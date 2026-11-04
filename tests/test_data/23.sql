WITH RECURSIVE fixed_parts AS
  (SELECT "b"."book_id" AS "b",
          "b"."char_range" AS "b_char_range",
          "b"."meta"->>'year' AS "b_year",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t"."char_range" AS "t_char_range",
          "t"."token_id" AS "t"
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1".segment8 AS s
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   WHERE "b"."char_range" && "s"."char_range"
     AND "s"."segment_id" = "t"."segment_id"
     AND ("b"."meta"->>'year')::numeric > (1910)::numeric ),
               match_list AS
  (SELECT "b_year"
   FROM fixed_parts),
               res1_g0 AS
  (SELECT "match_list"."b_year" AS "g0",
          count(*) AS v0
   FROM "match_list"
   GROUP BY ("match_list"."b_year")),
               res1_count_t2 AS
  (SELECT "match_list"."b_year" AS "g0",
          count(*) AS v0
   FROM "match_list"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t2"
   GROUP BY ("match_list"."b_year")),
               res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, "res1_g0"."g0", res1_g0.v0, res1_count_t2.v0)
   FROM "res1_g0"
   JOIN res1_count_t2 ON ("res1_g0"."g0" = "res1_count_t2"."g0")) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;
