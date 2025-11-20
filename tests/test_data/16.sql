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
     AND ("t_form"."form")::text = ('n''')::text
     AND "u_agent"."agent_id" = "u"."agent_id"
     AND ("u_agent"."agent"->>'annee_naissance')::text ~ concat('19[789][0-9]|2[0-9]', chr(123), '3', chr(125), '') ),
               match_list AS
  (SELECT fixed_parts."t" AS "t",
          fixed_parts."t_char_range" AS "t_char_range",
          fixed_parts."t_form" AS "t_form",
          fixed_parts."t_frame_range" AS "t_frame_range",
          fixed_parts."u" AS "u",
          fixed_parts."u_agent" AS "u_agent",
          fixed_parts."u_agent_annee_naissance" AS "u_agent_annee_naissance",
          fixed_parts."u_agent_region" AS "u_agent_region",
          fixed_parts."u_char_range" AS "u_char_range",
          fixed_parts."u_frame_range" AS "u_frame_range"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("u", jsonb_build_array("t") , array[lower(match_list."u_frame_range"), upper(match_list."u_frame_range")], array[lower(match_list."u_char_range"), upper(match_list."u_char_range")])
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(FALSE, "u_agent_annee_naissance", "u_agent_region", frequency)
   FROM
     (SELECT "u_agent_annee_naissance",
             "u_agent_region" ,
             count(*) AS frequency
      FROM match_list
      GROUP BY "u_agent_annee_naissance",
               "u_agent_region") x) ,
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
