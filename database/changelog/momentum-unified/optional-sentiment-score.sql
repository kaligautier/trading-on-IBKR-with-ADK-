--liquibase formatted sql
--changeset momentum:optional-sentiment-score
--comment: Unknown sentiment scores remain NULL rather than inventing a neutral score.
ALTER TABLE _analysis.sentiment_items ALTER COLUMN sentiment_score DROP NOT NULL;
--rollback ALTER TABLE _analysis.sentiment_items ALTER COLUMN sentiment_score SET NOT NULL;
