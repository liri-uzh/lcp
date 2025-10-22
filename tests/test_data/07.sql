WITH RECURSIVE fixed_parts AS
  (SELECT "e"."alignment_id" AS "e",
          "e"."char_range" AS "e_char_range",
          "e_aligned"."meta"->>'date' AS "e_aligned_date",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s"
   FROM "sparcling1".segment_enrest AS s
   CROSS JOIN "sparcling1"."session_en" "e"
   CROSS JOIN "sparcling1"."session_alignment" "e_aligned"
   WHERE "e"."alignment_id" = "e_aligned"."alignment_id"
     AND "e"."char_range" && "s"."char_range"
     AND (extract('year'
                  FROM ("e_aligned"."meta"->>'date')::date))::numeric > (1999)::numeric ),
               match_list AS
  (SELECT fixed_parts."e" AS "e",
          fixed_parts."e_aligned_date" AS "e_aligned_date",
          fixed_parts."e_char_range" AS "e_char_range",
          fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array())
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
