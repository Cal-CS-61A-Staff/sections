# Local Development

## Set Up
## Please work on a branch! After you've cloned the repo, make sure you've switched to the branch!

### Development with a Dev Container (Docker)
1. See main [README](../../README.md#docker-setup) for setup instructions.
2. Run command `bt sections_app`.
3. Install all Python requirements by running `pip3 install -r requirements.txt` inside of the [server directory](sections/server).
4. Now you can develop locally! Try it out with `yarn run dev` from `apps/sections`. Alternatively in seperate terminals, run the backend with `python3 main.py` from `apps/sections/server` and the frontend with `yarn start` from `apps/sections`.

### Development without a Dev Container (Docker)
1. Create symlinks in `berkeley-cs61a/apps/sections/server` and `berkeley-cs61a/apps/sections/src` by running `ln -s ../../../common common` within those directories.
2. Check your node version (bt is currently using v20.19.2), by running `node -v`.
4. Install yarn by running `npm install --global yarn`.
5. Download node requirements from [`package.json`](sections/package.json) with `yarn install`.
6. Create a new Python environment: `python3 -m venv venv`. If you name your virtual environment differently, make sure to update the [gitignore](sections/.gitignore).
7. Activate the new Python environment with `source venv/bin/activate`.
8. Install all Python requirements by running `pip3 install -r requirements.txt` inside of the [server directory](sections/server).
9. Now you can develop locally! Try it out with `yarn run dev` from `apps/sections`. Alternatively in seperate terminals, run the backend with `python3 main.py` from `apps/sections/server` and the frontend with `yarn start` from `apps/sections`.

## Authentication

If this is your first time developing the sections tool, you will need to ask for the environment variables not in this git repo-- CANVAS_SERVER_URL, CANVAS_CLIENT_ID, CANVAS_CLIENT_SECRET. These are used by OAuth to authenticate you into the Canvas sandbox so you can develop. Place these into an `.env` file, with ENV=DEV on the first line. Make sure to add the `.env` file to your `.gitignore`. If the below steps do not work, you will also need to ask to be added as an Admin to the canvas sandbox. Then, follow the instructions below.

To authenticate locally, click `Sign in`. You will be directed to something like `localhost:3000/oauth/canvas_login`. Change the link to use port 8000:
`localhost:8000/oauth/canvas_login`. Follow the link to authenticate with canvas. Now you can log in as normal. Once you get a redirect notice,
access `localhost:3000`. A jinja2 template not found exception is expected when you're accessing the server (port 8000) after authentication has completed.

### About the Sandbox

The production Sections app is deployed on GCP Cloud Run and interacts with bCourses. To locally mock this setup without exposing the production Canvas API keys, we use a "sandbox" Canvas instance located at [ucberkeleysandbox.instructure.com](https://ucberkeleysandbox.instructure.com/). During onboarding to the sections app, you will be added as an admin to the sandbox Canvas instance where you can view the development API key and create new API keys as needed.

**All development work should be done using the sandbox instance.** Access to bCourses should only be available in the production deployment once all testing with the sandbox is complete. You can do anything you'd like in the sandbox to simulate your desired testing environment (create courses, add students, specify user roles, etc.). You can make your own course, but we currently have a course  set up with users that can be found (after logging) by accessing the "Admin" button on the sidebar, then clicking "UC Berkeley Sandbox". Search through the courses for the one titled "Mango 101 (Deokpy Section)".

### More About Accessing Canvas APIs

Our wrapper to access Canvas APIs can be found at `sections/server/canvas_service/__init__.py`. The methods that our currently provisioned API key gives us permission to access can be found in [common/oauth_client.py](https://github.com/Cal-CS-61A-Staff/berkeley-cs61a/blob/e448458532f9dea5cc9b2077bde018beb1c90797/common/oauth_client.py#L174-L180).

bCourses API keys have strict scope and permissions. bCourses API keys should only be used for the exact purpose they were granted for. Specifically, the sections app API key should not be used by another app or for any purpose outside the approved scope for the sections app. If you need a new API key with broader scope or for a different app, please contact @pancakereport to discuss. The process for obtaining a new API key requires faculty or full time staff (like @pancakereport) support and working with RTL who manage bCourses. 

## Import Test Sections Locally

1. Start the server and front end.
2. Navigate to the `server` directory and run the following to import example sections and enrollment:

```
python3 import_locally.py --type sections --file test_csvs/test_sections.csv
python3 import_locally.py --type enrollment --file test_csvs/disc_enrollment.csv
python3 import_locally.py --type enrollment --file test_csvs/lab_enrollment.csv
```

3. Reload your localhost page, you should see the example sections locally.

## Import Sections from GCP
1. Download the sections database to obtain a `.sql` file. Relevant Links [1](https://cloud.google.com/sql/docs/mysql/import-export/import-export-sql) and [2](https://cloud.google.com/storage/docs/downloading-objects).
2. Likely the export uses MySQL syntax, so update it to SQLite.
3. In the `server` directory, delete `app.db` and run `sqlite3 app.db < gcp-sections-export.sql`.

## Notes
1. Use `yarn run flow` for typechecking.
2. If you'd to see debugging logs while the server is up and running, the usual `print` statements will not work. Instead, a method that currently works is described in this [commit](https://github.com/Cal-CS-61A-Staff/berkeley-cs61a/commit/0e75b8798543c0edd68cc02d1d9c1a9389105087).
3. If you run the app locally and sign in, you may need to update the local database to give yourself appropriate access levels to test the admin, staff, and student views. To assign yourself staff and admin access run the following (substituting your own email) *after* having already logged in:

    ```
    $ sqlite3 server/app.db
    $ sqlite> UPDATE user SET is_staff = 1, is_admin = 1 WHERE email = '<example>@berkeley.edu';
    $ sqlite> .exit
    ```
    If at any point you receive a error despite having mocked the proper permissions, you should clear your cookies at `localhost:3000` (Inspect page -> "Application" tab -> "Clear site data" button)
