WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."frame_range" AS "s_frame_range",
          "s"."segment_id" AS "s",
          "t"."char_range" AS "t_char_range",
          "t"."frame_range" AS "t_frame_range",
          "t"."token_id" AS "t",
          "top"."char_range" AS "top_char_range",
          "top"."frame_range" AS "top_frame_range",
          "top"."keywords" AS "top_keywords",
          "top"."topic_id" AS "top"
   FROM "cineminds_video_topic__0538f19753ba4303873463b0d6b3dace_3".segmentrest AS s
   CROSS JOIN "cineminds_video_topic__0538f19753ba4303873463b0d6b3dace_3"."topic" "top"
   CROSS JOIN
     (SELECT coalesce(bit_or(1::bit(328)<<bit)::bit(328), b'0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000') AS m
      FROM "cineminds_video_topic__0538f19753ba4303873463b0d6b3dace_3"."topic_labels"
      WHERE label = 'film') "top_mask_0"
   CROSS JOIN "cineminds_video_topic__0538f19753ba4303873463b0d6b3dace_3"."tokenrest" "t"
   WHERE "s"."char_range" && "top"."char_range"
     AND "top"."keywords" & "top_mask_0".m > 0::bit(328)
     AND "s"."segment_id" = "t"."segment_id" ),
               match_list AS
  (SELECT fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."s_frame_range" AS "s_frame_range",
          fixed_parts."t" AS "t",
          fixed_parts."t_char_range" AS "t_char_range",
          fixed_parts."t_frame_range" AS "t_frame_range",
          fixed_parts."top" AS "top",
          fixed_parts."top_char_range" AS "top_char_range",
          fixed_parts."top_frame_range" AS "top_frame_range",
          fixed_parts."top_keywords" AS "top_keywords"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("top", "t") , array[lower(match_list."s_frame_range"), upper(match_list."s_frame_range")], array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
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
