WITH RECURSIVE fixed_parts AS
  (SELECT "interruptee"."char_range" AS "interruptee_char_range",
          "interruptee"."frame_range" AS "interruptee_frame_range",
          "interruptee"."utterance_id" AS "interruptee",
          "interruptee_agent"."agent"->>'region' AS "interruptee_agent_region",
          "interruptor"."char_range" AS "interruptor_char_range",
          "interruptor"."frame_range" AS "interruptor_frame_range",
          "interruptor"."utterance_id" AS "interruptor",
          "interruptor_agent"."agent"->>'region' AS "interruptor_agent_region",
          "t"."char_range" AS "t_char_range",
          "t"."frame_range" AS "t_frame_range",
          "t"."token_id" AS "t"
   FROM "ofrom".utterancerest AS interruptor
   CROSS JOIN "ofrom"."utterancerest" "interruptee"
   CROSS JOIN "ofrom"."tokenrest" "t"
   CROSS JOIN "ofrom"."global_attribute_agent" "interruptee_agent"
   CROSS JOIN "ofrom"."global_attribute_agent" "interruptor_agent"
   WHERE "interruptee_agent"."agent_id" = "interruptee"."agent_id"
     AND "interruptor"."utterance_id" = "t"."utterance_id"
     AND "interruptor_agent"."agent_id" = "interruptor"."agent_id"
     AND ("interruptor"."utterance_id" != "interruptee"."utterance_id"
          AND "interruptor"."frame_range" && "interruptee"."frame_range"
          AND ((lower("interruptor"."frame_range") / 25.0))::numeric < ((upper("interruptee"."frame_range") / 25.0) - 1)::numeric ) ),
               match_list AS
  (SELECT fixed_parts."interruptee" AS "interruptee",
          fixed_parts."interruptee_agent_region" AS "interruptee_agent_region",
          fixed_parts."interruptee_char_range" AS "interruptee_char_range",
          fixed_parts."interruptee_frame_range" AS "interruptee_frame_range",
          fixed_parts."interruptor" AS "interruptor",
          fixed_parts."interruptor_agent_region" AS "interruptor_agent_region",
          fixed_parts."interruptor_char_range" AS "interruptor_char_range",
          fixed_parts."interruptor_frame_range" AS "interruptor_frame_range",
          fixed_parts."t" AS "t",
          fixed_parts."t_char_range" AS "t_char_range",
          fixed_parts."t_frame_range" AS "t_frame_range"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(interruptor, jsonb_build_array(t) , array[lower(match_list."interruptor_frame_range"), upper(match_list."interruptor_frame_range")])
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(interruptee_agent_region, interruptor_agent_region, frequency)
   FROM
     (SELECT interruptee_agent_region,
             interruptor_agent_region,
             count(*) AS frequency
      FROM match_list
      GROUP BY interruptee_agent_region,
               interruptor_agent_region) x) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2 ;