# Public product page

The `site/` directory is a static Cloudflare Pages site at https://keyrelay.colefoster.ca. The source has no server code or forms. Cloudflare Web Analytics collects basic traffic and performance data on the public page only; its beacon is allowed by the site CSP. The private credential broker has no analytics. Cloudflare may inject its own security challenge scripts at the edge. Manrope is self-hosted under the included SIL Open Font License.

Deploy from the repository root with a Cloudflare API token holding account-level Pages Write permission and the account ID supplied through `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`:

```sh
npx wrangler pages deploy site --project-name keyrelay --branch main
```

This is a direct-upload Pages project. Pushing to GitHub does not deploy it automatically.

The old `getkeyrelay.colefoster.ca` address redirects to the public domain. The private broker is at `key.colefoster.ca`.

The custom domain must be registered on the Pages project before creating its CNAME pointing to the project's `pages.dev` hostname.

`deploy.json` describes the separate private broker on ash; it is not the product-site deployment. The public site must never replace the private broker's DNS or expose its API.

Analytics dashboard: https://dash.cloudflare.com/254fb8570eaf32755d54128ed3904237/web-analytics/overview?siteTag=104ffa4d2d8240cebc598e9f4b980648
