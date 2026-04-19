I am creating an agent orchestration system that can work on coding projects by taking tasks and implementing them until they are done.
Пишем своего оркестратора агентов, который берёт задачу из бэклога, прогоняет ее через выбранный вами флоу и доводит до PR.

## Минимальные требования

Чтобы проект считался завершённым, оркестратор должен уметь:

- **Брать задачу из любого источника** – автоматически, из любого трекера или очереди на ваш выбор.
- **Писать код** – агент реализует задачу.
- **Создавать PR** – результат работы попадает в репозиторий.
- **Уходить на доработку** – если что-то пошло не так, система должна это обнаружить и попробовать исправить.
- **Работать на настоящем репозитории** – чтобы можно было показать результат на демо.

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

Minimal workflow:

The whole solution will work on tasks based on task*.md files where a task will be described including:
- requirements
- tech stack
- extra info

Orchestrator:
The orchestrator should scan the "tasks" directory where the task.md files will be placed and start implementing them one-by-one. 

Implementer:
The implementation should use the test-first approach, writing the full unit test with acceptance criteria before any implementation of the main code occurs. This should be done by an agent in a worktree and multiple agents of the same type can try to implement multiple tasks in parallel.

Checker:
After implementation a separate agent should go and run the build and all the tests.

If the build or tests fail, a fix should be implemented by the "Implementer".

After the checks are successful a PR in github should be created for this task.


