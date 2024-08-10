# Ladning

## Repo set up

1. Create and activate venv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install requirements:

```bash
pip install -r requirements-dev.txt
```

## Authenticating with Tesla API (generating OAuth token)

To generate the Tesla OAuth token, simply run the application (see below) on a PC with a browser available. A window
will pop-up in the browser and request Tesla sign-in. Once completed, copy the generated URL from the Tesla window and
paste it back into the input of `main.py` - then hit enter. The OAuth token will automatically be stored in `cache.json`
in the root of the repository for automatic authentication in the future.

If running headless (e.g. on a Raspberry-Pi), simply generate `cache.json` on a normal PC and copy it to the headless
machine.

## Running the application

To run, call `main.py` with the required arguments:

```shell
python main.py --easee_username [EASEE_USERNAME] --easee_password [EASEE_PASSWORD] --tesla_username [TESLA_USERNAME]
```

## Running the tests

To run tests, call:

```shell
python -m pytest .
```
