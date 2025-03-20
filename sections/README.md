# Local Development

## Set Up
## Please work on a branch! After you've cloned the repo, make sure you've switched to the branch!

### Development with a Dev Container
1. See main [README](../../README.md#docker-setup) for setup instructions.
2. Run command `bt sections_app`.
3. Install all Python requirements by running `pip3 install -r requirements.txt` inside of the [server directory](sections/server).
4. Now you can develop locally! Try it out with `yarn run dev` from `apps/sections`. Alternatively in seperate terminals, run the backend with `python3 main.py` from `apps/sections/server` and the frontend with `yarn start` from `apps/sections`.

### Development without a Dev Container (Docker)
1. Create symlinks in `berkeley-cs61a/apps/sections/server` and `berkeley-cs61a/apps/sections/src` by running `ln -s ../../../common common` within those directories.
2. [Download node js 16.](https://nodejs.org/en/download/package-manager)
3. Switch to 16 by running `nvm use 16.20.2`.
4. Install yarn by running `npm install --global yarn`.
5. Download node requirements from [`package.json`](sections/package.json) with `yarn install`.
6. Create a new Python environment: `python3 -m venv venv`. If you name your virtual environment differently, make sure to update the [gitignore](sections/.gitignore).
7. Activate the new Python environment with `source venv/bin/activate`.
8. Install all Python requirements by running `pip3 install -r requirements.txt` inside of the [server directory](sections/server).
9. Now you can develop locally! Try it out with `yarn run dev` from `apps/sections`. Alternatively in seperate terminals, run the backend with `python3 main.py` from `apps/sections/server` and the frontend with `yarn start` from `apps/sections`.

## Authentication

To authenticate locally, click `Sign in with OKPy`. You will be directed to something like `localhost:3000/oauth/login`. Change the link to use port 8000:
`localhost:8000/oauth/login`. This page will show you a link starting with `okpy.org/ouath...` that you click on. Now you can log in as normal. Once you get a redirect notice,
access `localhost:3000/oauth/login` again.

## Import Sections Locally

1. Start the server and front end
2. Run import_locally script using your csv file. Your csv should follow the template. Examples can be found [here](server/test_csvs)
Examples:
If importing sections:
`python3 import_locally.py --type sections --file path/to/your_file.csv`
If importing enrollment:
`python3 import_locally.py --type sections --file path/to/your_file.csv`

3. Reload your localhost page, you should see the updated sections locally.

## Notes
1. If you run the app locally and sign in, the app assumes you have admin access. This means you may not be able to test from the student view.
2. Use `yarn run flow` for typechecking.
