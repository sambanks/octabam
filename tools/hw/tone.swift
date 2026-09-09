// Play a sine on a named CoreAudio output device, every channel, for N seconds.
// usage: tone <freq_hz> <seconds> [device-substring] [amplitude 0..1] [on_ms period_ms]
// With on_ms/period_ms the tone is gated into bursts (5 ms raised-cosine edges): a
// rhythmic source with gaps, which is what a reverb or a delay is measured against.
// Built for the hardware seam capture: a steady tone out of the MicroBook into the
// Octatrack's inputs A/B, so a one-sample seam in a recorder loop is visible.
import AVFoundation
import CoreAudio
import Foundation

let args = CommandLine.arguments
guard args.count >= 3, let freq = Double(args[1]), let secs = Double(args[2]) else {
    FileHandle.standardError.write("usage: tone <freq_hz> <seconds> [device-substring] [amplitude]\n".data(using: .utf8)!)
    exit(1)
}
let want = args.count >= 4 ? args[3] : (ProcessInfo.processInfo.environment["REC_DEVICE"] ?? "MicroBook")
let amp = args.count >= 5 ? (Double(args[4]) ?? 0.25) : 0.25
let onMs = args.count >= 7 ? (Double(args[5]) ?? 0) : 0
let periodMs = args.count >= 7 ? (Double(args[6]) ?? 0) : 0

func findDevice(named want: String) -> AudioDeviceID? {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
                                          mScope: kAudioObjectPropertyScopeGlobal,
                                          mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var devs = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &devs)
    for d in devs {
        var nameAddr = AudioObjectPropertyAddress(mSelector: kAudioObjectPropertyName,
                                                  mScope: kAudioObjectPropertyScopeGlobal,
                                                  mElement: kAudioObjectPropertyElementMain)
        var cf: CFString = "" as CFString
        var csize = UInt32(MemoryLayout<CFString>.size)
        let err = withUnsafeMutablePointer(to: &cf) { p in
            AudioObjectGetPropertyData(d, &nameAddr, 0, nil, &csize, p)
        }
        if err == noErr && (cf as String).contains(want) { return d }
    }
    return nil
}

guard var dev = findDevice(named: want) else {
    FileHandle.standardError.write("\(want) not found\n".data(using: .utf8)!)
    exit(2)
}

let engine = AVAudioEngine()
let output = engine.outputNode
let au = output.audioUnit!
let err = AudioUnitSetProperty(au, kAudioOutputUnitProperty_CurrentDevice,
                               kAudioUnitScope_Global, 0, &dev,
                               UInt32(MemoryLayout<AudioDeviceID>.size))
guard err == noErr else {
    FileHandle.standardError.write("device select failed \(err)\n".data(using: .utf8)!)
    exit(3)
}
let fmt = output.outputFormat(forBus: 0)
let sr = fmt.sampleRate
var phase = 0.0
var n = 0
let step = 2.0 * Double.pi * freq / sr
let onN = Int(onMs * sr / 1000.0), periodN = Int(periodMs * sr / 1000.0), edgeN = Int(0.005 * sr)
func gate(_ i: Int) -> Double {
    if periodN <= 0 { return 1.0 }
    let k = i % periodN
    if k >= onN { return 0.0 }
    if k < edgeN { return 0.5 - 0.5 * cos(Double.pi * Double(k) / Double(edgeN)) }
    if k >= onN - edgeN { return 0.5 - 0.5 * cos(Double.pi * Double(onN - k) / Double(edgeN)) }
    return 1.0
}
let src = AVAudioSourceNode(format: fmt) { _, _, frameCount, audioBufferList -> OSStatus in
    let abl = UnsafeMutableAudioBufferListPointer(audioBufferList)
    for frame in 0..<Int(frameCount) {
        let v = Float(amp * gate(n) * sin(phase))
        n += 1
        phase += step
        if phase > 2.0 * Double.pi { phase -= 2.0 * Double.pi }
        for buf in abl {
            let p = buf.mData!.assumingMemoryBound(to: Float.self)
            p[frame] = v
        }
    }
    return noErr
}
engine.attach(src)
engine.connect(src, to: engine.mainMixerNode, format: fmt)
engine.connect(engine.mainMixerNode, to: output, format: fmt)
try! engine.start()
print("TONE \(freq) Hz on \(want) at \(sr) Hz x \(fmt.channelCount) ch, amp \(amp), \(secs) s" + (periodN > 0 ? ", bursts \(onMs)/\(periodMs) ms" : ""))
fflush(stdout)
Thread.sleep(forTimeInterval: secs)
engine.stop()
