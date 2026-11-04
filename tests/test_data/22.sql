WITH res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, "b"."meta"->>'year', "t_form"."form", count(*))
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."segment8" "s"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token_form" "t_form"
   WHERE ("b"."char_range" && "s"."char_range")
     AND ("s"."segment_id" = "t"."segment_id")
     AND (("b"."meta"->>'year')::numeric > (1910)::numeric)
     AND ("t_form"."form_id" = "t"."form_id")
   GROUP BY ("b"."meta"->>'year',
             "t_form"."form")),
     res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(res1.*))
   FROM res1)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;
