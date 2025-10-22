WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "s"."xy_box" AS "s_xy_box",
          "sm"."smudge_id" AS "sm",
          "sm"."xy_box" AS "sm_xy_box",
          "t"."char_range" AS "t_char_range",
          "t"."token_id" AS "t",
          "t"."xy_box" AS "t_xy_box"
   FROM "udhr_ocr_c789824360354006aa3cf723bed8d2db_1".segmentrest AS s
   CROSS JOIN "udhr_ocr_c789824360354006aa3cf723bed8d2db_1"."smudge" "sm"
   CROSS JOIN "udhr_ocr_c789824360354006aa3cf723bed8d2db_1"."tokenrest" "t"
   WHERE "s"."segment_id" = "t"."segment_id"
     AND "s"."xy_box" && "sm"."xy_box" ),
               match_list AS
  (SELECT fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."s_xy_box" AS "s_xy_box",
          fixed_parts."sm" AS "sm",
          fixed_parts."sm_xy_box" AS "sm_xy_box",
          fixed_parts."t" AS "t",
          fixed_parts."t_char_range" AS "t_char_range",
          fixed_parts."t_xy_box" AS "t_xy_box"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t"))
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
