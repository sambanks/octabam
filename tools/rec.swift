// Drop-free recorder pinned to the EVO4: CoreAudio device lookup by name,
// AVAudioEngine tap -> int32 PCM wav (all input channels).
// usage: rec <seconds> <out.wav>   Prints "START <epoch>" once live.
import AVFoundation
import CoreAudio
import Foundation

let args = CommandLine.arguments
guard args.count >= 3, let secs = Double(args[1]) else {
    FileHandle.standardError.write("usage: rec <seconds> <out.wav>\n".data(using: .utf8)!)
    exit(1)
}
let url = URL(fileURLWithPath: args[2])
try? FileManager.default.removeItem(at: url)

func findDevice(named want: String) -> AudioDeviceID? {
    var addr = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var devs = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &devs)
    for d in devs {
        var nameAddr = AudioObjectPropertyAddress(
            mSelector: kAudioObjectPropertyName,
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

guard var dev = findDevice(named: "EVO4") else {
    FileHandle.standardError.write("EVO4 not found\n".data(using: .utf8)!)
    exit(2)
}

let engine = AVAudioEngine()
let input = engine.inputNode
let au = input.audioUnit!
let err = AudioUnitSetProperty(au, kAudioOutputUnitProperty_CurrentDevice,
                               kAudioUnitScope_Global, 0, &dev,
                               UInt32(MemoryLayout<AudioDeviceID>.size))
guard err == noErr else {
    FileHandle.standardError.write("device select failed \(err)\n".data(using: .utf8)!)
    exit(3)
}

let fmt = input.inputFormat(forBus: 0)
let settings: [String: Any] = [
    AVFormatIDKey: kAudioFormatLinearPCM,
    AVSampleRateKey: fmt.sampleRate,
    AVNumberOfChannelsKey: fmt.channelCount,
    AVLinearPCMBitDepthKey: 32,
    AVLinearPCMIsFloatKey: false,
    AVLinearPCMIsNonInterleaved: false,
]
var file: AVAudioFile? = try! AVAudioFile(forWriting: url, settings: settings)
var written: AVAudioFramePosition = 0

input.installTap(onBus: 0, bufferSize: 4096, format: fmt) { buf, _ in
    do { try file?.write(from: buf); written += AVAudioFramePosition(buf.frameLength) }
    catch { FileHandle.standardError.write("write error\n".data(using: .utf8)!) }
}

try! engine.start()
print("START \(Date().timeIntervalSince1970) rate \(fmt.sampleRate) ch \(fmt.channelCount)")
fflush(stdout)
Thread.sleep(forTimeInterval: secs)
engine.stop()
input.removeTap(onBus: 0)
file = nil   // release -> finalize WAV header
print("DONE frames \(written) = \(Double(written)/fmt.sampleRate)s (asked \(secs)s)")
