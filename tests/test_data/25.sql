WITH res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(FALSE, "d"."meta"->>'classCode', sum(greatest(0, jsonb_array_length("n gram".content) - 1)))
   FROM "bnc1"."document" "d"
   CROSS JOIN LATERAL
     (SELECT *
      FROM "bnc1"."segmentrest" "s"
      WHERE "d"."char_range" && "s"."char_range") "s"
   CROSS JOIN "bnc1"."prepared_segment" "n gram"
   WHERE ("d"."meta"->>'classCode' ~ 's')
     AND ("s"."segment_id" = "n gram"."segment_id")
   GROUP BY ("d"."meta"->>'classCode')),
     res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(res1.*))
   FROM res1)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;