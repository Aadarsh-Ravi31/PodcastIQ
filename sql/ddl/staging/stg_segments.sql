-- STAGING.STG_SEGMENTS — FLATTEN segments array → one row per transcript line
-- Source: RAW.EPISODES segments array (~1M rows across 250+ episodes)
-- Cleans noise markers: [Music], [Applause], [Laughter], HTML entities

CREATE OR REPLACE VIEW PODCASTIQ.STAGING.STG_SEGMENTS (
    VIDEO_ID,
    CHANNEL_ID,
    CHANNEL_NAME,
    GENRE,
    DURATION_MIN,
    SEGMENT_INDEX,
    TEXT_RAW,
    TEXT_CLEAN,
    START_TIME,
    DURATION_SEC,
    END_TIME,
    IS_ARTIFACT,
    SEGMENT_ID
) AS (
    WITH raw AS (
        SELECT
            raw_data:video_id::VARCHAR(20)      AS video_id,
            raw_data:channel_id::VARCHAR(30)    AS channel_id,
            raw_data:channel_name::VARCHAR(100) AS channel_name,
            raw_data:genre::VARCHAR(50)         AS genre,
            raw_data:duration_min::FLOAT        AS duration_min,
            raw_data:segments                   AS segments
        FROM PODCASTIQ.RAW.EPISODES
        WHERE raw_data:segments IS NOT NULL
    ),

    flattened AS (
        SELECT
            r.video_id,
            r.channel_id,
            r.channel_name,
            r.genre,
            r.duration_min,
            f.index                                AS segment_index,
            f.value:text::VARCHAR                  AS text_raw,

            -- Clean: remove noise markers and HTML entities
            TRIM(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        f.value:text::VARCHAR,
                        '\\[Music\\]|\\[Applause\\]|\\[Laughter\\]|\\[Cheering\\]|\\[Inaudible\\]',
                        '', 1, 0, 'i'
                    ),
                    '&amp;|&gt;|&lt;|&nbsp;', ' '
                )
            )                                      AS text_clean,

            f.value:start::FLOAT                   AS start_time,
            f.value:duration::FLOAT                AS duration_sec,
            f.value:start::FLOAT +
                f.value:duration::FLOAT            AS end_time,

            -- Flag artifact segments
            CASE
                WHEN f.value:text::VARCHAR ILIKE '%[Music]%'
                  OR f.value:text::VARCHAR ILIKE '%[Applause]%'
                  OR f.value:text::VARCHAR ILIKE '%[Laughter]%'
                THEN TRUE ELSE FALSE
            END                                    AS is_artifact,

            -- Composite segment ID: video_id + zero-padded index
            r.video_id || '_' ||
                LPAD(f.index::VARCHAR, 5, '0')     AS segment_id

        FROM raw r,
        LATERAL FLATTEN(input => r.segments) f

        -- Filter: skip very short segments and empty text
        WHERE f.value:duration::FLOAT > 0.05
          AND LENGTH(TRIM(f.value:text::VARCHAR)) > 2
    )

    SELECT * FROM flattened
);
