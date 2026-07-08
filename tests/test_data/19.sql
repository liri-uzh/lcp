WITH RECURSIVE fixed_parts AS
  (SELECT "d"."char_range" AS "d_char_range",
          "d"."document_id" AS "d",
          "d"."meta"->>'classCode' AS "d_classCode",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1_form"."form" AS "t1_form"
   FROM "bnc1".segmentrest AS s
   CROSS JOIN "bnc1"."document" "d"
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."form" "t1_form"
   WHERE "d"."char_range" && "s"."char_range"
     AND "s"."segment_id" = "t1"."segment_id"
     AND "t1_form"."form_id" = "t1"."form_id"
     AND ("d"."meta"->>'classCode')::text ~ '^S'
     AND ("t1_form"."form")::text = ('hello')::text ),
               match_list AS
  (SELECT "s",
          "s_char_range",
          "t1"
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
