WITH RECURSIVE fixed_parts AS
  (SELECT "k1"."frame_range" AS "k1_frame_range",
          "k1"."kinesics" AS "k1_kinesics",
          "k1"."kinesics_id" AS "k1",
          "k1_speaker"."speaker" AS "k1_speaker",
          "k2"."frame_range" AS "k2_frame_range",
          "k2"."kinesics" AS "k2_kinesics",
          "k2"."kinesics_id" AS "k2",
          "k2_speaker"."speaker" AS "k2_speaker",
          "s"."char_range" AS "s_char_range",
          "s"."frame_range" AS "s_frame_range",
          "s"."segment_id" AS "s",
          "s_speaker"."speaker" AS "s_speaker",

     (SELECT array_agg("contained_token"."token_id")
      FROM "candor__5003f209a11e4737ae21a00cb8857736_3"."tokenrest" "contained_token"
      WHERE "s"."char_range" && "contained_token"."char_range" ) AS "s_container"
   FROM "candor__5003f209a11e4737ae21a00cb8857736_3".segmentrest AS s
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."kinesics" "k1"
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."global_attribute_speaker" "k1_speaker"
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."kinesics" "k2"
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."global_attribute_speaker" "k2_speaker"
   CROSS JOIN "candor__5003f209a11e4737ae21a00cb8857736_3"."global_attribute_speaker" "s_speaker"
   WHERE "k1"."frame_range" && "k2"."frame_range"
     AND (("k2"."kinesics")::text = ('smile')::text
          AND "k2"."speaker_id" = "k1"."speaker_id")
     AND "k1"."frame_range" && "s"."frame_range"
     AND "k2"."frame_range" && "s"."frame_range"
     AND "s"."speaker_id" != "k1"."speaker_id"
     AND "k1_speaker"."speaker_id" = "k1"."speaker_id"
     AND "k2_speaker"."speaker_id" = "k2"."speaker_id"
     AND "s_speaker"."speaker_id" = "s"."speaker_id"
     AND ("k1"."kinesics")::text = ('nod_yes')::text ),
               match_list AS
  (SELECT fixed_parts."k1" AS "k1",
          fixed_parts."k1_frame_range" AS "k1_frame_range",
          fixed_parts."k1_kinesics" AS "k1_kinesics",
          fixed_parts."k1_speaker" AS "k1_speaker",
          fixed_parts."k2" AS "k2",
          fixed_parts."k2_frame_range" AS "k2_frame_range",
          fixed_parts."k2_kinesics" AS "k2_kinesics",
          fixed_parts."k2_speaker" AS "k2_speaker",
          fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."s_container" AS "s_container",
          fixed_parts."s_frame_range" AS "s_frame_range",
          fixed_parts."s_speaker" AS "s_speaker"
   FROM fixed_parts),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(s_container) , array[lower(match_list."s_frame_range"), upper(match_list."s_frame_range")])
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