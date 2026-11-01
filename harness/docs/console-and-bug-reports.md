# Xbox builds, GSC bug reports, mod.io

Console builds are not made by modders: GSC cooks them from the mod's source zip after a request on the **Zone Kit
support desk**, and uploads the Xbox build to the mod's mod.io page. The same desk takes bug reports. Verified with
several requests and 2 bug reports, 2026-10-21 → 10-27. Site: `https://zonekit-support.stalker2.com/en-US/support/tickets`
(the old Zendesk `/hc/en-us/requests/new?ticket_form_id=...` URL is a 404 since 2026-10-21).

## Xbox build request
### Before the form
1. **Publish on mod.io first.** The request needs the mod's public mod.io page. The page URL is
   `https://mod.io/g/stalker2/m/<slug>`; the slug is fixed when the mod is created and does not follow a rename. Take
   the URL mod.io reports (`profile_url` from `GET /games/5761/mods/<id>`), never build it from the mod's name (two
   tickets got wrong links that way).
2. **The source zip on a shareable link.** Zip the contents of the mod's plugin folder
   `<kit>\Stalker2\Mods\<Mod>\` (`<Mod>.uplugin`, `Content\` with the `.uasset`s and loose `.cfg`s, `Resources\`) at
   the zip root, and upload it somewhere "anyone with the link can view" (the form asks for a Google Drive URL). Asset mods
   reach ~125 MB. Do not file the request without the link.
   - If the last cook logged missing-asset warnings, sort that out first: the form asks you to confirm there are none.
3. **One ticket per mod.** Open the tickets list (signed in) and search for the mod name (subjects usually
   `XBOX Mod Cooking Request: <Mod>`; check older wordings too). An **open** ticket for the mod → send the update as a
   reply there (new zip link + mod.io link). Only closed ones → file a new request.

### The form (`.../support/tickets/create`)
| Field | Value |
|---|---|
| Category (top dropdown; pick first, the mod fields appear after) | `New mod / Mod update` |
| Name*, Email* | only shown when signed out: the modder's name and contact email (ask them; never store it in a repo) |
| Subject* | `XBOX Mod Cooking Request: <Mod>` |
| Description* | e.g. `Requesting Xbox cooking for the mod "<Mod>" by <author>. The zip is linked in the Google Drive field. Thanks!` |
| Your Name (how to address you) | the author's name |
| URL to Google Drive with a mod* | the zip link |
| URL to mod's page on mod.io | `https://mod.io/g/stalker2/m/<slug>#description` |
| Malicious files or inappropriate content check* | checkbox: an attestation |
| Reference confirmation* | text field (was a checkbox), e.g. `Confirmed: the mod has no references to missing assets.` |
| Attachments | none |
- **The two attestations are the modder's statements.** Show them the filled form and get their explicit go-ahead
  before ticking them and pressing Submit (a standing instruction from the modder counts, e.g. "release on all
  platforms includes the Xbox request").
- Signed in: Name/Email disappear, a CCs field appears above the Drive field, and Submit opens the new ticket
  (`/support/tickets/<id>`): report its number. Signed out: only "Thank you for contacting us.", the confirmation
  goes by email. Opened directly by URL the create page can look signed out (no avatar, Name/Email shown) while the
  ticket still lands on the account; judge sign-in from the tickets list.
- GSC replies on the ticket once the Xbox build is on mod.io; nothing else is needed.

### Form quirks (browser automation, 2026-10-22)
- Clicks right after navigation are ignored while the page hydrates: wait / screenshot, then click.
- Picking the category reloads the field list (spinner); wait before typing, or the form can collapse without the mod
  fields (only a reload fixes it).
- Typing the Subject opens an "Are you looking for this?" list that pushes the Description down.
- The Description is a rich-text editor: setting the value programmatically does not stick; click into it and type, or
  dispatch a synthetic `paste` event carrying `text/html`. `/` opens a command list; a line starting with `- ` becomes
  a list and keeps the dash on following items (type list items without dashes).
- Leaving a filled form opens a "Leave site?" dialog that freezes the tab: work in a new tab.
- Never resubmit a request that went through, even to fix its subject.

## Bug reports to GSC
Same site, **Category `Support request`**: Subject, Operating System & Version, Hardware Specifications (CPU / RAM /
GPU), Description, **Issue Type `Bug`** (or `Question`), attachments up to 20 MB (larger files as a shareable link).
Submitting with an attachment takes ~30 s and opens `/support/tickets/<id>`. Write it as a reproducible game/kit bug:
what you did, what happened, what should happen, kit and game version, logs.
Replying on a ticket: click "Add message" (opens the editor), paste, **Update**; with no attachment it asks "Attachment
Missing" → **Send Anyway**.

## mod.io (distribution; the Xbox build lives there too)
- Game id **5761** (`stalker2`). REST API base from your mod.io API access; OAuth bearer token. Create a mod:
  `POST /games/5761/mods` (name, summary, description HTML, logo); edit: `POST /games/5761/mods/<id>` (`visible=1`
  makes it public); add a file: `POST /games/5761/mods/<id>/files` multipart with `filedata` (zip), `version`,
  `changelog`, `platforms[]`, `active=true`.
- The PC file is the staged cook output: zip `<kit>\Stalker2\SavedMods\Staged\<Mod>\Windows\` so the archive holds
  `Windows\{OverrideContent,NewContent}\Windows\...` (`pipeline.md` §5). (The source's uploads tagged it
  `platforms[] = windows, xboxseriesx`; whether `xboxseriesx` is needed on the PC file is unverified.)
- A mod's file list mixes PC and the Xbox builds GSC uploads: to fetch a shipped PC build, pick the newest file whose
  `platforms` include `windows` (the newest one can be Xbox-only). Some older mod.io zips also carry a stale pre-2.0
  `Stalker2\` folder next to `Windows\`: ship only `Windows\`.
- Fetching a published build from mod.io's API is the reliable route; `steamcmd` Workshop downloads wait on Steam Guard
  approval and timed out.

## Linux / Proton
Nothing differs: the support desk, mod.io and the Drive upload were all driven from a Linux browser and shell. The zip
is built from the kit plugin folder inside the prefix's view of `<kit>` (or the repo mirror of it).
