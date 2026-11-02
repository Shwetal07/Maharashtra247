# Maharashtra 24/7 – setup (free, no server needed)
1. Create a GitHub account → New repository (name: maharashtra247) → upload all files in this folder (keep the .github folder).
2. Repository → Settings → Pages → Source: "Deploy from a branch" → main / root.
3. Repository → Actions tab → "Update news" → Run workflow. After ~1 minute news.json appears; it then refreshes every 15 minutes.
4. Your site is live at https://<your-username>.github.io/maharashtra247/ . Later, connect your own domain in Settings → Pages.

## Control sources
Edit feeds.json. Test feeds on your computer:  pip install -r requirements.txt && python fetch_news.py --check
Add your own stories in manual.json, for example:
[{"id":"m1","title":"नाशिकमध्ये ...","summary":"...","cat":"नाशिक","source":"आपला रिपोर्टर","link":"https://...","img":"","ts":1793606400000}]
For your own YouTube video use  "yt":"VIDEO_ID"  in the item.

## Admin panel (publish your own news, photos, YouTube videos)
1. Create a token: GitHub -> Settings -> Developer settings -> Fine-grained tokens -> Generate. Pick ONLY this repository, Permissions -> Contents: Read and write.
2. Open https://<your-username>.github.io/maharashtra247/admin.html , enter "yourname/maharashtra247" and the token, press Save.
3. Fill the form and press Publish. The story appears on the site in 1-2 minutes. Use the bin icon to remove one.
The token stays only in your browser. Never share it. Do not use the admin page on a shared computer.
