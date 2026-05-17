import { defineCliConfig } from 'sanity/cli'

export default defineCliConfig({
  api: {
    projectId: 'n4dgl02q',
    dataset: 'production'
  },
  deployment: {
    appId: 'v9i4hr48ddw5p63wea2jao6j',
    /**
     * Enable auto-updates for studios.
     * Learn more at https://www.sanity.io/docs/studio/latest-version-of-sanity#k47faf43faf56
     */
    autoUpdates: true,
  }
})
