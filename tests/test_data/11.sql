WITH RECURSIVE fixed_parts AS
  (SELECT "nod"."frame_range" AS "nod_frame_range",
          "nod"."kinesics" AS "nod_kinesics",
          "nod"."kinesics_id" AS "nod",
          "s"."char_range" AS "s_char_range",
          "s"."frame_range" AS "s_frame_range",
          "s"."segment_id" AS "s",
          "t"."char_range" AS "t_char_range",
          "t"."frame_range" AS "t_frame_range",
          "t"."token_id" AS "t",
          "t"."upos" AS "t_upos"
   FROM "candor__5003f209a11e4737ae21a00cb8857736_3".segmentrest AS s
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."kinesics" "nod"
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."tokenrest" "t"
   WHERE NOT EXISTS
       (SELECT 1
        FROM "candor__5003f209a11e4737ae21a00cb8857736_3"."kinesics" "nod"
        WHERE "s"."frame_range" && "nod"."frame_range"
          AND ("nod"."kinesics")::text ~ 'nod' )
     AND "s"."segment_id" = "t"."segment_id"
     AND ("t"."upos")::text = ('DET')::text ),
               match_list AS
  (SELECT fixed_parts."nod" AS "nod",
          fixed_parts."nod_frame_range" AS "nod_frame_range",
          fixed_parts."nod_kinesics" AS "nod_kinesics",
          fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."s_frame_range" AS "s_frame_range",
          fixed_parts."t" AS "t",
          fixed_parts."t_char_range" AS "t_char_range",
          fixed_parts."t_frame_range" AS "t_frame_range",
          fixed_parts."t_upos" AS "t_upos"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(t) , array[lower(match_list."s_frame_range"), upper(match_list."s_frame_range")])
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