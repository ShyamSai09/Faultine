# Getting it running

Written for someone who has never opened a terminal before. Every command is given in full.

---

## What you need

| Thing | Why | Free? |
| --- | --- | --- |
| Python 3.11 or newer | Runs the program | Yes |
| A Hindsight account | The memory system | Yes, with a promo code |
| About 4 minutes | Mostly waiting for the first run | |

You do **not** need Docker, Node, a GPU, or a credit card.

---

## Step 1: get Python

Check whether you have it:

```bash
python3 --version
```

If you see a number like `3.12.4`, you are done. If you see "command not found", install it:

- **Mac**: `brew install python` (or download from python.org)
- **Windows**: download the installer from python.org, and tick "Add Python to PATH"
- **Linux**: `sudo apt install python3 python3-venv`

## Step 2: get a Hindsight account

Faultline stores its memory on Hindsight's servers. Sign up at
**https://ui.hindsight.vectorize.io**

Then:

1. Go to the billing or credits page
2. Enter promo code **`MEMHACK99`** for $50 of free credit
3. Find your API key and copy it. It starts with `hsk_`
4. The base URL is `https://api.hindsight.vectorize.io`

Keep that key somewhere safe. You are about to paste it into a file.

### Prefer not to sign up?

There is an offline mode that needs no account at all:

```bash
HINDSIGHT_API_LLM_PROVIDER=llamacpp
HINDSIGHT_API_LLM_MODEL=gemma-4-e2b-it
```

It downloads a model of about 3.5 GB on first run and is much slower. Everything works. Use it if
you want the project to run with no keys and no internet, or if you want to show a judge it works
without any account at all.

## Step 3: open a terminal in the project folder

```bash
cd ~/Desktop/hacakthons/faultline
```

(On Windows: `cd %USERPROFILE%\Desktop\hacakthons\faultline`)

## Step 4: make a private space for the packages

A "virtual environment" is just a private folder for this project's dependencies, so they do not
collide with anything else on your machine.

```bash
python3 -m venv .venv
```

Nothing prints. That is success.

## Step 5: install the packages

```bash
.venv/bin/pip install -r requirements.txt
```

**On Windows**, use backslashes: `.venv\Scripts\pip install -r requirements.txt`

This takes one to three minutes. It downloads a few hundred megabytes, including a sentence
embedding model and a text ranking model that Hindsight uses for searching. Those download
themselves on first use, so there is a wait the first time you start the server.

## Step 6: create your settings file

```bash
cp .env.example .env
```

Now open `.env` in any text editor and put in your key:

```
HINDSIGHT_API_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=hsk_your_actual_key_here
```

Delete the other lines or leave them, they are comments.

> **Do not paste your key into `.env.example`.** That file goes on the internet. Only `.env` is
> private, and it is already excluded from version control.

## Step 7: start it

```bash
./run.sh
```

On Windows: `.venv\Scripts\python -m uvicorn app.main:app --port 8000`

**The first start takes 30 to 60 seconds** while it loads the search models. This is normal and
only happens once. Watch for:

```
Application startup complete
```

Then open **http://localhost:8000** in your browser. The landing page explains the project; the
live console is at **http://localhost:8000/console**.

You will see a progress bar. It is loading nineteen incidents into memory. That takes two to four
minutes the first time, because every one of them is processed by a language model. Watch the
stage names change:

```
creating banks
retaining incidents          1/19 ... 19/19
retaining service state      1/4 ... 4/4
retaining remediation backlog
consolidating observations
ready
```

After that it is instant, because the memory is already on the server.

## Step 8: see it work

1. Open http://localhost:8000/console
2. Press the **Triage alert** button
3. Wait about five seconds
4. Read the three things that appeared

Then, to see the contrast, drag the **Memory** switch to off and press the button again.

---

## Everyday commands

```bash
# start
./run.sh

# start with automatic reload while you edit
.venv/bin/python -m uvicorn app.main:app --port 8000 --reload

# start without the browser opening a server at all
.venv/bin/python scripts/smoke_test.py

# verify the memory layer works, in isolation
.venv/bin/python scripts/smoke_test.py
```

To stop the server, click the terminal window and press `Control` and `C` together.

---

## If something goes wrong

Go to [TROUBLESHOOTING.md](TROUBLESHOOTING.md). The most common ones:

| Symptom | Cause | Fix |
| --- | --- | --- |
| "No .env found" | Step 6 not done | `cp .env.example .env` then add your key |
| "Invalid API key" | Key wrong, or has a typo | Copy it again from the Hindsight dashboard |
| "429 quota exceeded" | Out of credit | Add the promo code, or check your balance |
| Progress bar stuck at "retaining incidents 1/19" | The model call is failing | Check your key and your credit |
| "Timeout context manager should be used inside a task" | A threading bug | Already handled in the code. If you see it, you changed something in `app/memory.py` |
| Port 8000 already in use | Another program has it | `./run.sh --port 8001` or stop the other program |
| Blank page | JavaScript error | Open the browser's developer console and reload |

---

## What to do before showing it to anyone

1. Run it once, fully, so the memory is loaded and the first-run wait is done
2. Confirm **Hindsight Cloud** shows in the top right of the console
3. Press Triage once and check the match percentage is high
4. Press Triage once with memory off, so the contrast is ready to show
5. Open the Learning curve tab and check the numbers are there
6. Zoom your browser to 125% if you are projecting

That is the whole setup. Next: [SCREENS.md](SCREENS.md)
