--liquibase formatted sql

--changeset deep-copy:momentum-trader-ratio-text-001 dbms:postgresql
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 SELECT CASE WHEN current_database() = 'momentum' THEN 1 ELSE 0 END;
--comment: The Trader contract permits an explanatory risk/reward string, without a length cap.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE _analysis.trader_proposals ALTER COLUMN risk_reward_ratio TYPE TEXT;

--rollback ALTER TABLE _analysis.trader_proposals ALTER COLUMN risk_reward_ratio TYPE VARCHAR(20);
