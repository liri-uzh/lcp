WITH match_list AS
  (SELECT "b"."meta"->>'year' AS a0,
          "t_form"."form" AS a1,
          count(*) AS frequency
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."segment8" "s"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token_form" "t_form"
   WHERE ("b"."char_range" && "s"."char_range")
     AND ("s"."segment_id" = "t"."segment_id")
     AND (("b"."meta"->>'year')::numeric > (1910)::numeric)
     AND ("t_form"."form_id" = "t"."form_id")
   GROUP BY (("b"."meta"->>'year',
              "t_form"."form"))
   ORDER BY frequency DESC),
     res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, a0, a1, frequency)
   FROM match_list),
     res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(SUM(match_list.frequency))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;
