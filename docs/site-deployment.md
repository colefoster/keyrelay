# Public product page

The `site/` directory is a static Cloudflare Pages site at https://getkeyrelay.colefoster.ca. It has no server code, forms, analytics, or third-party runtime requests. Manrope is self-hosted under the included SIL Open Font License.

Deploy from the repository root with a Cloudflare API token holding account-level Pages Write permission and the account ID supplied through `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`:

```sh
npx wrangler pages deploy site --project-name keyrelay --branch main
```

This is a direct-upload Pages project. Pushing to GitHub does not deploy it automatically.

The custom domain must be registered on the Pages project before creating its CNAME pointing to the project's `pages.dev` hostname.

`deploy.json` describes the separate private broker on ash; it is not the product-site deployment. The public site must never replace the private broker's DNS or expose its API.
