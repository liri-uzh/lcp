WITH res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, count(*))
   FROM "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."book" "b"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."segment8" "s"
   CROSS JOIN "text_berg_korpus_echo_des_alples_1e01737e3ada4407892cb804a7ce5900_1"."token8" "t"
   WHERE ("b"."char_range" && "s"."char_range")
     AND ("s"."segment_id" = "t"."segment_id")
     AND (("b"."meta"->>'year')::numeric > (1910)::numeric) ),
     res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(*))
   FROM res1)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;