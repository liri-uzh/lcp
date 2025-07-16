# This file contains English translations for the LCP platform.

## --------------- GENERAL ---------------

platform-general = LiRI Corpus Platform
platform-general-short = LCP
platform-catchphrase = catchphrase
platform-soundscript = soundscript
platform-videoscope = videoscope

platform-general-description =
 The LiRI Corpus Platform (LCP) is a software system for handling and querying corpora of different kinds. Users can query corpora directly from their browser, and upload their
 own corpora using a command-line interface.
platform-general-no-permission = You currently don't have permissions to query this corpus. Please see the corpus description to learn how to gain access.
platform-general-access-restricted = Access to this corpus is restricted. We need you to log in to evaluate your permissions.
platform-general-fetched-results = The first pages of results have been fetched. More results will be fetched if you move to the next page or if you hit Search whole corpus.
platform-general-find-corpora = Find Corpora
platform-general-corpus-edit = Corpus edit
platform-general-corpus-license = Corpus licence
platform-general-user-license = Corpus licence: User defined - Check details
platform-general-corpus-details = Corpus details
platform-general-corpus-settings = Corpus settings
platform-general-corpus-origin = Corpus origin
platform-general-data-type = Data type

## --------------- USER PAGE ---------------

platform-user-saved-query-description =
 Here you can view and delete the queries you've saved. Saved queries are divided by type: Text, DQD or CQP, select the corresponding tab to view all queries of a given type.

## --------------- COMMON ---------------

common-user = { $count ->
 *[one] User
 [other] Users
}
common-user-info = User information
common-name = Name
common-email = Email
common-organization = Organization
common-admin = Admin
common-login = Login
common-logout = Logout
common-active = Active
common-ready = Ready
common-ok = Ok
common-invited = Invited
common-invite = Invite
common-remove = Remove
common-key = Key
common-secret = Secret
common-help-1 = Your secret will not be visible after closing this window.
common-help-2 = The secret will be shown just once. Copy the secret to the safe place.
common-match = Match
common-details = Details
common-close = Close
common-stop = Stop
common-save = Save
common-plain-query = Query (e.g. a cat)
common-cqp-query = Query (e.g. [word="hello"])
common-save-query = Save query
common-saved-queries = Saved queries
common-select-saved-queries = Select a saved query
common-select-saved-queries-dropdown = Select a query from the dropdown..
common-select-no-saved-queries = You don't have any saved queries of this type.
common-delete-query-sure = Are you sure you want to delete this query?
common-delete-query = Delete query
common-submit = Submit
common-resubmit = Resubmit
common-copy-clipboard = Copy to clipboard
common-loading = Loading
common-loading-data = Loading data
common-data = Data
common-loading-results = Loading results
common-previous = Previous
common-next = Next
common-select-document = Select document
common-corpus = Corpus
corpus-structure = Corpus structure
common-select-corpus = Select corpus
common-corpora = Corpora
common-query = Query
common-query-name = Query name
common-query-result = Query result
common-total-progress = Total progress
common-refresh-progress = Refresh progress bar
common-show-hide-corpus = Show/hide corpus structure
common-timeline = Timeline
common-show-timeline = View timeline
load-example-query = Load example query
common-query-corpus = Query corpus
common-go-to-time = Go to time
common-loading-video-duration = Loading video duration
common-frame = Frame
common-time = Time
common-add-group = Add new group
common-group-settings = Group settings
common-start-date = Start date
common-finish-date = Finish date
common-institution = Institution
common-enabled = Enabled
common-disabled = Disabled
common-description = Description
common-partition = Partition
common-word-count = Word count
common-revision = Revision
common-languages = Languages
common-export = Export
common-export-results = Export results
common-launch-export = Launch export
common-search-whole = Search whole corpus
common-number-results = Number of results
common-projected-results = Projected results
common-batch-done = Batch done
common-status = Status
common-dont-show-again = Don't show this again
common-no-results = No results found
common-plain = Plain
common-plain-format = Plain format
common-download-preview = Download preview
common-text = Text
common-rotate-device = Please rotate your device to view the timeline

common-play-audio = Play audio
common-play-video = Play video
common-zoom-out = Zoom Out
common-zoom-in = Zoom In
common-zoom-reset-default = Reset default
common-zoom-fit-content = Fit content

common-yes = Yes
common-no = No
common-mandatory-fields = Mandatory fields

## --------------- MENU ---------------

menu-home = Home
menu-query = Query
menu-viewer = Viewer
menu-manual = Manual

## --------------- MODALS ---------------

# Corpus details modal

modal-details-count = Word count
modal-details-revison = Revison
modal-details-url = URL
modal-details-description = Description
modal-details-language = Main language
modal-details-partitions = Partitions
modal-details-segments = Segments
modal-details-license = License
modal-details-user-license = User defined

# Metadata edit modal

modal-meta-metadata = Metadata
modal-meta-structure = Structure
modal-meta-swissubase = SWISSUbase
modal-meta-group = Group
modal-meta-name = Name
modal-meta-url = URL
modal-meta-authors = Authors
modal-meta-provider = Provider/Institution
modal-meta-revision = Revision
modal-meta-data-type = Data type
modal-meta-description = Description
modal-meta-language = Main language
modal-meta-license = License
modal-meta-user-defined = User defined
modal-meta-user-license = User defined license
modal-meta-sample = Sample DQD query
modal-meta-warning-before = You are currently editing the properties in
modal-meta-warning-after = . Switch the interface's language to edit the properties in another language.
modal-meta-lg-undefined = Undefined
modal-meta-lg-english = English
modal-meta-lg-german = German
modal-meta-lg-french = French
modal-meta-lg-italian = Italian
modal-meta-lg-spanish = Spanish
modal-meta-lg-swiss-german = Swiss German
modal-meta-lg-romansh = Romansch
modal-structure-no-desc = No Description

modal-swissubase-header-1 = Publish your data directly to SWISSUbase using this form. To proceed, please provide the required information in the fields below.
modal-swissubase-header-warning = Once your submission has been transferred from LCP to SWISSUbase, it can no longer be edited in LCP. Please note that the submission process is not yet complete at this stage. Since only the metadata is transferred to SWISSUbase, you still need to log in to the SWISSUbase web interface to finalize and complete the submission manually.
modal-swissubase-api-access-token = SWISSUbase Access Token
modal-swissubase-project-id = SWISSUbase Project ID
modal-swissubase-dataset-title = Dataset Title
modal-swissubase-dataset-language = Dataset Language
modal-swissubase-dataset-description = Description
modal-swissubase-request-doi = Request DOI
modal-swissubase-dateset-documentation-remarks = Documentation Remarks
modal-swissubase-dataset-version-note = Version Note
modal-swissubase-dataset-url = Dataset URL
modal-swissubase-resource-type = Resource type
modal-swissubase-resource-description = Resource description
modal-swissubase-resource-keywords = Keywords
modal-swissubase-resource-validation-information = Validation information
modal-swissubase-resource-validation-information = Validation information
modal-swissubase-tab-project = Project
modal-swissubase-tab-dataset = Dataset
modal-swissubase-tab-resource = Resource
modal-swissubase-tab-usage-license = Usage Licence
modal-swissubase-confirm-text = Confirm that I have the right to publish this corpus on SWISSUbase
modal-swissubase-confirm-info = Please complete all required fields and verify the API access token.
modal-swissubase-submit-button = Send the data to SWISSUbase
modal-swissubase-already-submitted = The data for this corpus has already been submitted to SWISSUbase on project ID
modal-swissubase-verify-api-token = Verify API Token and Project ID
modal-swissubase-invalid-project = The project is not valid
modal-swissubase-valid-project = The API access token and project are valid

# New/Edit project modal

modal-project-new = New Group
modal-project-title = Title
modal-project-title-error =
 Title is mandatory (min. length is seven letters).
 Title will be manually checked. Try to be concise and informative.
modal-project-start-date = Start date
modal-project-start-date-error = Start date is mandatory.
modal-project-end-date = End date
modal-project-end-date-error = End date is mandatory.
modal-project-description = Description
modal-project-description-placeholder = Please describe the purpose of your group
modal-project-tab-metadata = Metadata
modal-project-tab-permissions = Permissions
modal-project-tab-api = API
modal-project-data-request-public = Request to Make Data Public
modal-project-invitation = (invitation sent to { $email })
modal-project-invited = Invited users
modal-project-invite = Invite people
modal-project-invite-placeholder = Email (comma-separated list of email addresses)
modal-project-invite-help = Separate multiple email addresses with a comma.
modal-project-issued = Issued on
modal-project-revoke-key = Revoke API Key
modal-project-create-key = Create API Key

# Results details modal

modal-results-tab-graph = Dependency Graph
modal-results-tab-tabular = Tabular

# Results components

results-kwic-right-context = Right context
results-image-viewer = Image Viewer
results-audio-no-support = Your browser does not support the audio element.
results-plain-filter-placeholder = Filter by

# Footer

footer-report = Report a bug
