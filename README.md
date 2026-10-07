# byosdesign.com

Static site, deployed to the Cloudflare Worker `flat-morning-0e75` on every push to `main`.

- `public/`: everything that gets served. `index.html` is the page.
- `public/_redirects`: short links (`byosdesign.com/go/...`) printed in the plans. One line per link; always 302. Edit the destination to repoint every plan at once.
- `wrangler.jsonc`: deploy config. Don't rename the Worker.
