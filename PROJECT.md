# Intro 
We are writing our own agent orchestrator that takes a task from the backlog, runs it through a flow of your choice, and brings it to a PR.

## Minimal Requirements
For the project to be considered complete, the orchestrator must be able to:

Take a task from any source – automatically, from any tracker or queue of your choice.

Write code – the agent implements the task.

Create a PR – the result of the work is delivered to the repository.

Go back for revisions – if something goes wrong, the system must detect it and attempt to fix it.

Work on a real repository – so that the result can be demonstrated.

## Task management tool for this project:

Linear with CLI access described in https://github.com/schpet/linear-cli

Linear project URL https://linear.app/aihackersprint/team/AIH/active

## Git for this project

The whoole project git repo: https://github.com/podlodka-ai-club/the-smelters

The demo project on which the orchestrator will work on to implement tasks: https://github.com/podlodka-ai-club/the-smelters/DemoProject

Use "gh" CLI for accessing git

## Examples of existing orchestrators:
https://github.com/egv/yolo-runner
https://github.com/stepango/grkr

## Project mind map

https://app.holst.so/board/2f7472e9-dffd-463f-9656-738d0a2a73d9

## Tech stack:
Agent to be used in the orchestrator: Claude code CLI/ OpenCode CLI. Google Gemini API key via opencode CLI or Anthropic Claude code cli with subscription.

The orchestrator should be written in Python with pip3 and pevn3

Database to be used - SQLite

## The type of projects the orchestrator and agent will going to work on:

Android Kotlin projects that have clean architecture and an AGENTS.md explaining the project setup

## The orchestrators workflows:

### Minimal workflow:

The whole solution will work on tasks based on task*.md files where a task will be described including:
- requirements
- tech stack
- extra info

### Orchestrator:
The orchestrator should scan the "tasks" directory where the task.md files will be placed and start implementing them one-by-one. 

### Implementer:
The implementation should use the test-first approach, writing the full unit test with acceptance criteria before any implementation of the main code occurs. This should be done by an agent in a worktree and multiple agents of the same type can try to implement multiple tasks in parallel.

### Checker:
After implementation a separate agent should go and run the build and all the tests.

If the build or tests fail, a fix should be implemented by the "Implementer".

After the checks are successful a PR in github should be created for this task.


## Initial project state:

Read README.md for current project details.

In the root dir exists a python project https://github.com/podlodka-ai-club/the-smelters

Currently, it uses the Claude Agent SDK, so it works either with a Claude subscription or via a Claude API key.

What needs to be done:
1. Add the project name to the tasks: Project: DemoApp
2. Verify that the agent can handle the new task name format; if not, unify the tasks to a single format — currently they are in different formats.
3. Add support for other agents.
4. Start writing android_coder and android_reviewer — everything is described in the README.

### How it works:

#### Setup:
uv venv
uv pip install -e ".[dev]"

#### Migrate tasks from the tasks folder to SQLite
.venv/bin/python seed.py

#### Run the orchestrator, which monitors tasks in SQLite and picks them up one by one; it runs forever until you kill the process
.venv/bin/python orchestrator.py --watch

#### In another terminal, run the dashboard to view logs and task statuses
.venv/bin/python tui.py

