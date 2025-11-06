# release-job
Add a label to all Uclusion jobs listed in commits in a release. For performance reasons, the query for commits goes 
back only as many days as the workspace has set for its Completed Task display.

Example:

```
name: Mark jobs with stage label

on:
  release:
    types: [published]

jobs:
  markJobsStageLabel:
    if: startsWith(github.event.release.tag_name, 'stage')
    runs-on: ubuntu-latest
    environment:
      name: "stage"
    steps:
      - name: Mark jobs released
        uses: Uclusion/release-job@v1
        with:
          secret_key_id: ${{ secrets.SECRET_KEY_ID }}
          secret_key: ${{ secrets.SECRET_KEY }}
          workspace_id: ${{ secrets.WORKSPACE_ID }}
          git_token: ${{ secrets.GIT_TOKEN }}
          git-sha: ${{ github.sha }}
          git-repository: ${{ github.repository }}
          label: "Deployed to stage"
```
