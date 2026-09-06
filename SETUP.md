# GitHub profile setup

This repository does not require Python or Pillow to be installed on your computer. GitHub Actions installs `requirements.txt` automatically.

## 1. Revoke any token that was pasted or shared

If a personal access token has ever been pasted into a chat, issue, commit, screenshot, or other message, revoke it before continuing. Do not reuse it.

## 2. Create the contribution token

On GitHub, create a **Personal access token (classic)** owned by `bitreonx` with only the scope required here:

- `read:user`

Do not commit the token into any file.

## 3. Add the Actions secret

In `bitreonx/bitreonx`:

1. Open **Settings**.
2. Open **Secrets and variables → Actions**.
3. Choose **New repository secret**.
4. Name it exactly `PROFILE_TOKEN`.
5. Paste the newly created classic token and save.

## 4. Allow the workflow to update the profile

Open **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**.

The workflow uses the built-in Actions checkout credential only for committing generated README/assets. It is never used as a contribution-data fallback.

## 5. Run the refresh

Open **Actions → Refresh profile → Run workflow**.

The run will:

1. install Python 3.12 and `requirements.txt`;
2. run the full test suite;
3. require `PROFILE_TOKEN`;
4. verify the token belongs to `bitreonx` and has `read:user`;
5. fetch the owner-authenticated GitHub contribution calendar;
6. verify daily counts sum exactly to GitHub's `totalContributions`;
7. render the optimized light/dark assets;
8. update README/assets only when the generated output changed.

If token validation or data integrity fails, the workflow exits without replacing the last valid profile.
