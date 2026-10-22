import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const [sourcePath, outputDir] = process.argv.slice(2);
if (!sourcePath || !outputDir) throw new Error("Usage: inspect-deck.mjs <source.pptx> <output-dir>");
await fs.mkdir(outputDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({
  kind: "deck,slide,textbox,shape,image,table,chart,notes,layout",
  maxChars: 60000,
});
await fs.writeFile(path.join(outputDir, "inspect.ndjson"), snapshot.ndjson, "utf8");
const slideCount = presentation.slides.items.length;
console.log(`SLIDE_COUNT=${slideCount}`);
for (let index = 0; index < slideCount; index += 1) {
  const slide = presentation.slides.getItem(index);
  const preview = await slide.export({ format: "png", scale: 1 });
  await fs.writeFile(path.join(outputDir, `slide-${index + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
}
console.log(snapshot.ndjson);
