from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "tile_info" (
    "id" INT NOT NULL PRIMARY KEY,
    "tile_x" INT NOT NULL,
    "tile_y" INT NOT NULL,
    "queue_temperature" INT NOT NULL DEFAULT 999,
    "last_checked" INT NOT NULL DEFAULT 0,
    "last_update" INT NOT NULL,
    "http_etag" VARCHAR(255) NOT NULL DEFAULT ''
) /* Persistent metadata for a single WPlace tile. */;
CREATE INDEX IF NOT EXISTS "idx_tile_info_queue_t_d49c98" ON "tile_info" ("queue_temperature", "last_checked");
        CREATE TABLE IF NOT EXISTS "tile_project" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "project_id" INT NOT NULL REFERENCES "project_info" ("id") ON DELETE CASCADE,
    "tile_id" INT NOT NULL REFERENCES "tile_info" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_tile_projec_tile_id_75ba4e" UNIQUE ("tile_id", "project_id")
) /* Many-to-many relationship between tiles and projects. */;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "tile_project";
        DROP TABLE IF EXISTS "tile_info";"""


MODELS_STATE = (
    "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"
)
