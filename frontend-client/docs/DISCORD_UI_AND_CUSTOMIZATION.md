# DRCK config and Discord-style UI

## Using the DRCK variant

This repo includes a **DRCK** variant so the desktop app uses your homeserver and branding by default.

### 1. Edit the config (your server URLs)

Edit **one** of these (they are the same; use the one you prefer):

- **`config/drck/config.json`** – for `--cfgdir config/drck`
- **`element.io/drck/config.json`** – for `--cfgdir element.io/drck`

Set your real values:

- **`default_server_name`** – your Matrix server name (e.g. `matrix.mycompany.com`)
- **`default_server_config.m.homeserver.base_url`** – Synapse client URL (e.g. `https://matrix.mycompany.com`)
- **`element_call.url`** – Element Call URL (e.g. `https://call.matrix.mycompany.com` from your enterprise stack)
- **`room_directory.servers`** – optional list of room directory servers

### 2. Fetch the webapp with this config

```bash
yarn install
yarn run fetch --cfgdir element.io/drck --noverify
```

(Or use `config/drck` instead of `element.io/drck`.)

### 3. Run locally

```bash
yarn run build:ts
yarn run build:res
yarn start
```

### 4. Build a packaged app (optional)

To build installers with DRCK branding and protocol:

```bash
export VARIANT_PATH=element.io/drck/build.json
yarn run build
```

Output will be in `dist/` (e.g. `drck-desktop` executable, DRCK as product name).

---

## Discord-style layout (Servers left, Members right, “Servers” label)

**Important:** Element **Desktop** is only the Electron shell. All UI (sidebar, room list, member list, labels like “Rooms” or “Spaces”) comes from **Element Web**, which is loaded as the webapp (e.g. from `webapp.asar`).

So:

- **Renaming “Rooms” to “Servers”**, **putting the server/space list on the left**, and **member list on the right** with **Discord-like buttons and menus** must be done in **Element Web** (or a fork of it), not in this repo.

### Options

1. **Fork Element Web**  
   Clone [element-web](https://github.com/element-hq/element-web), then:
   - Change terminology (e.g. “Spaces”/“Rooms” → “Servers”) in the UI strings.
   - Adjust layout (e.g. move space list to the left, member list to the right, Discord-style controls) in the React components and CSS.
   - Build the webapp (`yarn build`), then point this desktop app at it (see below).

2. **Use this desktop with your Element Web build**  
   After building your customized Element Web:
   - Either symlink:  
     `ln -s /path/to/element-web/webapp ./webapp`  
     in the **element-desktop** (frontend-client) directory, then run `yarn run build:ts && yarn run build:res && yarn start`.
   - Or copy your built webapp into a folder named `webapp` here; the desktop app will use it instead of `webapp.asar` if present.

3. **Theming / labs**  
   Element Web supports themes and some layout options. For a full Discord-like layout (server list left, members right, custom menus), code and layout changes in Element Web are required; there is no single config flag in Element Desktop or Element Web that does this.

### Summary

| What you want              | Where to do it        |
|---------------------------|------------------------|
| Default homeserver, brand  | This repo: DRCK config |
| Discord layout & “Servers”| Element Web (or fork) |
| Desktop packaging/branding| This repo: DRCK variant + `VARIANT_PATH` |
