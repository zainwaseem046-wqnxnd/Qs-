# Clearview QS website

Marketing website for **Clearview QS**, an independent cost consultancy. It is a static site
(plain HTML, CSS and a little JavaScript) with no build step, separate from the QS Intelligence app in this repo.

```
website/
  index.html    all page content (hero, services, approach, sectors, about, contact)
  styles.css    styling and responsive layout
  script.js     mobile menu, scroll effects, contact-form handling
  favicon.svg   site icon
```

## Preview locally

```bash
cd website && python3 -m http.server 8080   # then open http://localhost:8080
```

## Before going live

- Enquiries go to Clearviewqs@gmail.com (set in `index.html`).
- The contact form opens the visitor's email app addressed to the email shown on the page. To receive
  submissions directly instead, point the form at a form service (e.g. Formspree or Netlify Forms).
- The cost report figures in the hero are labelled as an illustrative example.

## Hosting

Upload the `website/` folder to any static host: Netlify, Vercel, Cloudflare Pages, GitHub Pages or
ordinary shared hosting.

### GitHub Pages (set up in this repo)

`.github/workflows/website.yml` deploys this folder to GitHub Pages whenever `website/` changes on the
default branch. One-time setup: in the repository on GitHub go to **Settings → Pages** and set
**Source** to **GitHub Actions**, then merge this branch (or run the workflow from the Actions tab).
The site will be at `https://zainwaseem046-wqnxnd.github.io/Qs-/`. To use your own domain such as
`clearviewqs.co.uk`, add it under **Settings → Pages → Custom domain** and point your DNS at GitHub.
