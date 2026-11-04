// The web builder page: give it your own OCTATRACK_OS1.40C zip, download the
// card image of the release the manifest names. Everything runs in this browser tab.
import { build } from "./builder.js";
import { makeEft } from "./eft-run.js";

const root = document.getElementById("octabam-builder");
const el = (tag, attrs = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), attrs);
  n.append(...kids);
  return n;
};
const here = (p) => new URL(p, import.meta.url);

async function main() {
  const manifest = await (await fetch(here("manifest.json"))).json();

  const meta = manifest.remixes[0];
  const file = el("input", { type: "file", id: "ob-file", accept: ".zip,.syx", hidden: true });
  const choose = el("button", { type: "button", id: "ob-choose", textContent: "Choose OS file" });
  const chosen = el("span", { id: "ob-chosen", textContent: " No file chosen." });
  const go = el("button", { id: "ob-go", textContent: "Build", disabled: true });
  const status = el("p", { id: "ob-status", role: "status" });
  const links = el("p", { id: "ob-links" });
  const built = el("p", { className: "ob-meta" },
    `Built from the ${manifest.version} release, commit ${manifest.commit.slice(0, 8)}, ${manifest.date}.`);

  root.replaceChildren(
    el("p", {}, `Octabam ${manifest.version}`),
    el("p", {}, "Your OCTATRACK_OS1.40C_dist.zip or OCTATRACK_OS1.40C.syx:"),
    el("p", {}, choose, chosen, file),
    el("p", {}, go), status, links, built);

  choose.addEventListener("click", () => file.click());
  file.addEventListener("change", () => {
    go.disabled = !file.files.length;
    chosen.textContent = ` ${file.files.length ? file.files[0].name : "No file chosen."}`;
  });

  go.addEventListener("click", async () => {
    go.disabled = true;
    links.replaceChildren();
    try {
      const bytes = new Uint8Array(await file.files[0].arrayBuffer());
      const patch = new Uint8Array(await (await fetch(here(meta.patch))).arrayBuffer());
      const createModule = (await import("./eft.mjs")).default;
      const r = await build({
        file: bytes, patch, meta, eft: makeEft(createModule),
        onStep: (s) => { status.textContent = s + "..."; },
      });
      status.textContent = "Done. Nothing was uploaded; the files below exist only in this tab.";
      const dl = (data, name, label) => el("a", {
        href: URL.createObjectURL(new Blob([data], { type: "application/octet-stream" })),
        download: name, textContent: label,
      });
      links.append(
        dl(r.bin, r.names.bin, `${r.names.bin} (card)`), " · ",
        dl(r.syx, r.names.syx, `${r.names.syx} (MIDI)`), " · ",
        dl(r.rmx, r.names.rmx, `${r.names.rmx} (REMIX SWITCH)`));
    } catch (e) {
      status.textContent = `Failed: ${e.message}`;
    } finally {
      go.disabled = !file.files.length;
    }
  });
}

main().catch((e) => { root.textContent = `The builder could not start: ${e.message}`; });
