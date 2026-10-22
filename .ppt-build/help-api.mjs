import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const source = process.argv[2];
const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
for (const query of ["remove delete shape", "slide shapes collection", "shape add", "table add", "connectors add", "image add"]) {
  console.log(`\n### ${query}\n`);
  console.log((await presentation.help(query, { maxChars: 5000 })).ndjson);
}
