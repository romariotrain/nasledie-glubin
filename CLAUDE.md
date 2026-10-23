# Наследие глубин — вход для Claude Code

Прочитай `AGENTS.md`, затем `docs/production/HANDOFF.md` и
`docs/production/README.md`. Последние два файла описывают подтверждённую базу
на 23.10.2026; старые README описывают свои исторические версии.

Текущий Unity-проект: `unity/SwordsmanCombatTest`, Unity 6000.6.6f1, Built-in.
Рабочая сцена: `Assets/SwordsmanTest/Scenes/DungeonCombatTest.unity`.
Мечник: `art/characters/swordsman/hunyuan_combat_v010`.
Доказательства: `unity/SwordsmanCombatTest/Validation/dungeon_v003`.
Бег 4.3 м/с; idle не следует мыши, движение задаёт направление, атака/выпад — курсор.

Начни с `git status --short` и чтения receipt. При наличии локальной Python-среды:

```powershell
& './work/hunyuan2mini/.venv/Scripts/python.exe' tools/character_pipeline/audit_baseline.py
```

Не начинать персонажа/проект заново, не импортировать эксперимент v008 и не менять
рендер-пайплайн в рамках иной задачи. Политика root motion уже определена: перемещение
кодом. Сохранять предыдущие версии, .meta и конкретные результаты проверок.

Рабочая практика: `docs/production/AGENT_WORKFLOW.md`.
Уроки: `docs/production/RETROSPECTIVE_2026-10-23.md`.
Дальнейшие возможности: `docs/production/ROADMAP.md` — предложения, не команда
автоматически устанавливать инструменты или выполнять весь бэклог.

Git пока не отслеживает исходники игры/ассеты/инструменты; один текущий clone
может содержать только документы. Не утверждать, что база восстановима, без проверки.
Unity CLI есть, Pipeline package не подключён; обычный чат Claude без файловых
инструментов не получает доступ к редактору только от чтения этой инструкции.
