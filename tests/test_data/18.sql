WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1_form"."form" AS "t1_form"
   FROM "bnc1".segmentrest AS s
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."form" "t1_form"
   WHERE "s"."segment_id" = "t1"."segment_id"
     AND ("t1_form"."form")::text ILIKE 'may%'
     AND ("t1_form"."form")::text ~* '^may$'
     AND "t1_form"."form_id" = "t1"."form_id" ),
               match_list AS
  (SELECT fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."t1" AS "t1",
          fixed_parts."t1_char_range" AS "t1_char_range",
          fixed_parts."t1_form" AS "t1_form"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t1") , array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
   FROM match_list) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;