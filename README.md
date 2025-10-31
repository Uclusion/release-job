# release-job
Add a label to all Uclusion jobs listed in commits in a release. Example:

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
      - name: Mark job complete
        uses: Uclusion/release-job@v1
        with:
          secret_key_id: ${{ secrets.SECRET_KEY_ID }}
          secret_key: ${{ secrets.SECRET_KEY }}
          workspace_id: ${{ secrets.WORKSPACE_ID }}
          git_token: ${{ secrets.GIT_TOKEN }}
          label: 'Released on stage'
          github-event-message: ${{ github.event.release.tag_name }}
```