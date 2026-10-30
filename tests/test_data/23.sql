WITH match_list AS
  (SELECT "b"."meta"->>'year' AS a0,
          "b"."char_range" AS "b_char_range",
          "s"."char_range" AS "s_char_range",
          count(*) AS frequency
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."segment8" "s"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   WHERE ("b"."char_range" && "s"."char_range")
     AND ("s"."segment_id" = "t"."segment_id")
     AND (("b"."meta"->>'year')::numeric > (1910)::numeric)
   GROUP BY (("b"."char_range",
              "s"."char_range",
              "b"."meta"->>'year'))
   ORDER BY frequency DESC),
     res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, a0, frequency)
   FROM match_list
   UNION SELECT 1::int2 AS rstype,
                jsonb_build_array(TRUE, a0, count("t"."token_id"))
   FROM match_list
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t" WHERE("b_char_range" && "t"."char_range")
   AND ("s_char_range" && "t"."char_range")
   GROUP BY (a0)),
     res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(SUM(match_list.frequency))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;
