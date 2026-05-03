from teams_ui.chat_app import app


if __name__ == "__main__":
    import uvicorn

    from teams_ui.config import TeamsSettings

    settings = TeamsSettings.from_env()
    uvicorn.run(
        "teams_chat_app:app",
        host=settings.host,
        port=settings.chat_port,
    )
