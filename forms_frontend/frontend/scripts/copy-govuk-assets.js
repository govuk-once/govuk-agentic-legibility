/**
 * Copy GOV.UK Frontend static assets (fonts, images) to public/assets/
 * so they're available at /assets/ as GOV.UK Frontend expects.
 */
import { cpSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const govukDist = join(root, "node_modules", "govuk-frontend", "dist", "govuk");
const publicAssets = join(root, "public", "assets");

mkdirSync(join(publicAssets, "fonts"), { recursive: true });
mkdirSync(join(publicAssets, "images"), { recursive: true });

cpSync(join(govukDist, "assets", "fonts"), join(publicAssets, "fonts"), {
  recursive: true,
});
cpSync(join(govukDist, "assets", "images"), join(publicAssets, "images"), {
  recursive: true,
});

console.log("GOV.UK Frontend assets copied to public/assets/");
