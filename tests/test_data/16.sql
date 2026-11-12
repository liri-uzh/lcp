WITH RECURSIVE fixed_parts AS
  (SELECT "t"."char_range" AS "t_char_range",
          "t"."frame_range" AS "t_frame_range",
          "t"."token_id" AS "t",
          "t_form"."form" AS "t_form",
          "u"."char_range" AS "u_char_range",
          "u"."frame_range" AS "u_frame_range",
          "u"."utterance_id" AS "u",
          "u_agent"."agent" AS "u_agent",
          "u_agent"."agent"->>'annee_naissance' AS "u_agent_annee_naissance",
          "u_agent"."agent"->>'region' AS "u_agent_region"
   FROM "ofrom".utterancerest AS u
   CROSS JOIN "ofrom"."global_attribute_agent" "u_agent"
   CROSS JOIN "ofrom"."tokenrest" "t"
   CROSS JOIN "ofrom"."token_form" "t_form"
   WHERE "t_form"."form_id" = "t"."form_id"
     AND "u"."utterance_id" = "t"."utterance_id"
     AND "t_form"."form" = 'n'''
     AND "u_agent"."agent"->>'annee_naissance' ~ concat('19[789][0-9]|2[0-9]', chr(123), '3', chr(125), '')
     AND "u_agent"."agent_id" = "u"."agent_id" ),
               match_list AS
  (SELECT "t",
          "u",
          "u_agent_annee_naissance",
          "u_agent_region",
          "u_char_range",
          "u_frame_range"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("u", jsonb_build_array("t") , array[lower(match_list."u_frame_range"), upper(match_list."u_frame_range")], array[lower(match_list."u_char_range"), upper(match_list."u_char_range")])
   FROM match_list) ,
               res2_g0_g1 AS
  (SELECT "match_list"."u_agent_annee_naissance" AS "g0",
          "match_list"."u_agent_region" AS "g1",
          count(*) AS v0
   FROM "match_list"
   GROUP BY ("match_list"."u_agent_annee_naissance",
             "match_list"."u_agent_region")),
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(FALSE, "res2_g0_g1"."g0", "res2_g0_g1"."g1", res2_g0_g1.v0)
   FROM "res2_g0_g1") ,
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