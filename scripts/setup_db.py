from app.db.migrations import upgrade_database


def main() -> None:
    upgrade_database()
    print("Database migrated to latest version")


if __name__ == "__main__":
    main()