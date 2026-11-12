WITH RECURSIVE fixed_parts AS
  (SELECT "a"."article_id" AS "a",
          "a"."char_range" AS "a_char_range",
          "b"."book_id" AS "b",
          "b"."char_range" AS "b_char_range",
          "b"."meta"->>'year' AS "b_year",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1_form"."form" AS "t1_form"
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1".segment8 AS s
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t1"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token_form" "t1_form"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."article" "a"
   WHERE "a"."char_range" && "s"."char_range"
     AND "b"."char_range" && "a"."char_range"
     AND "s"."segment_id" = "t1"."segment_id"
     AND "t1_form"."form" ~ '^(Per|Da)'
     AND "t1_form"."form_id" = "t1"."form_id" ),
               match_list AS
  (SELECT "b_char_range",
          "b_year",
          "s",
          "s_char_range",
          "t1"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t1") , array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
   FROM match_list) ,
               res2_g0 AS
  (SELECT "match_list"."b_year" AS "g0",
          count(*) AS v0
   FROM "match_list"
   GROUP BY ("match_list"."b_year")),
               res2_count_t AS
  (SELECT "match_list"."b_year" AS "g0",
          count(*) AS v0
   FROM "match_list"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   WHERE "t"."char_range" && b_char_range
   GROUP BY ("match_list"."b_year")),
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(FALSE, "res2_g0"."g0", res2_g0.v0, res2_count_t.v0)
   FROM "res2_g0"
   JOIN res2_count_t ON ("res2_g0"."g0" = "res2_count_t"."g0")) ,
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