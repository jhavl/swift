# import argparse
# import asyncio
# import json
# import logging
# import os
# import ssl
# import uuid

# # from av import VideoFrame
# # from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
# # from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay

# ROOT = os.path.dirname(__file__)

# # logger = logging.getLogger("pc")
# # pcs = set()
# # relay = MediaRelay()


# # class VideoTransformTrack(MediaStreamTrack):
# #     """
# #     A video stream track that transforms frames from an another track.
# #     """

# #     kind = "video"

# #     def __init__(self, track, transform):
# #         super().__init__()  # don't forget this!
# #         self.track = track
# #         self.transform = transform

# #     async def recv(self):
# #         frame = await self.track.recv()

# #         if self.transform == "cartoon":
# #             img = frame.to_ndarray(format="bgr24")

# #             # prepare color
# #             img_color = cv2.pyrDown(cv2.pyrDown(img))
# #             for _ in range(6):
# #                 img_color = cv2.bilateralFilter(img_color, 9, 9, 7)
# #             img_color = cv2.pyrUp(cv2.pyrUp(img_color))

# #             # prepare edges
# #             img_edges = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
# #             img_edges = cv2.adaptiveThreshold(
# #                 cv2.medianBlur(img_edges, 7),
# #                 255,
# #                 cv2.ADAPTIVE_THRESH_MEAN_C,
# #                 cv2.THRESH_BINARY,
# #                 9,
# #                 2,
# #             )
# #             img_edges = cv2.cvtColor(img_edges, cv2.COLOR_GRAY2RGB)

# #             # combine color and edges
# #             img = cv2.bitwise_and(img_color, img_edges)

# #             # rebuild a VideoFrame, preserving timing information
# #             new_frame = VideoFrame.from_ndarray(img, format="bgr24")
# #             new_frame.pts = frame.pts
# #             new_frame.time_base = frame.time_base
# #             return new_frame
# #         elif self.transform == "edges":
# #             # perform edge detection
# #             img = frame.to_ndarray(format="bgr24")
# #             img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)

# #             # rebuild a VideoFrame, preserving timing information
# #             new_frame = VideoFrame.from_ndarray(img, format="bgr24")
# #             new_frame.pts = frame.pts
# #             new_frame.time_base = frame.time_base
# #             return new_frame
# #         elif self.transform == "rotate":
# #             # rotate image
# #             img = frame.to_ndarray(format="bgr24")
# #             rows, cols, _ = img.shape
# #             M = cv2.getRotationMatrix2D((cols / 2, rows / 2), frame.time * 45, 1)
# #             img = cv2.warpAffine(img, M, (cols, rows))

# #             # rebuild a VideoFrame, preserving timing information
# #             new_frame = VideoFrame.from_ndarray(img, format="bgr24")
# #             new_frame.pts = frame.pts
# #             new_frame.time_base = frame.time_base
# #             return new_frame
# #         else:
# #             return frame


# # async def offer(request):
# #     params = await request.json()
# #     offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

# #     pc = RTCPeerConnection()
# #     pc_id = "PeerConnection(%s)" % uuid.uuid4()
# #     pcs.add(pc)

# #     def log_info(msg, *args):
# #         logger.info(pc_id + " " + msg, *args)

# #     log_info("Created for %s", request.remote)

# #     # prepare local media
# #     player = MediaPlayer(os.path.join(ROOT, "demo-instruct.wav"))
# #     recorder = MediaBlackhole()

# #     @pc.on("datachannel")
# #     def on_datachannel(channel):
# #         @channel.on("message")
# #         def on_message(message):
# #             if isinstance(message, str) and message.startswith("ping"):
# #                 channel.send("pong" + message[4:])

# #     @pc.on("connectionstatechange")
# #     async def on_connectionstatechange():
# #         log_info("Connection state is %s", pc.connectionState)
# #         if pc.connectionState == "failed":
# #             await pc.close()
# #             pcs.discard(pc)

# #     @pc.on("track")
# #     def on_track(track):
# #         log_info("Track %s received", track.kind)

# #         if track.kind == "audio":
# #             pc.addTrack(player.audio)
# #             recorder.addTrack(track)
# #         elif track.kind == "video":
# #             pc.addTrack(
# #                 VideoTransformTrack(
# #                     relay.subscribe(track), transform=params["video_transform"]
# #                 )
# #             )
# #             if args.record_to:
# #                 recorder.addTrack(relay.subscribe(track))

# #         @track.on("ended")
# #         async def on_ended():
# #             log_info("Track %s ended", track.kind)
# #             await recorder.stop()

# #     # handle offer
# #     await pc.setRemoteDescription(offer)
# #     await recorder.start()

# #     # send answer
# #     answer = await pc.createAnswer()
# #     await pc.setLocalDescription(answer)

# #     return web.Response(
# #         content_type="application/json",
# #         text=json.dumps(
# #             {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
# #         ),
# #     )


# async def on_shutdown(app):
#     # close peer connections
#     coros = [pc.close() for pc in pcs]
#     await asyncio.gather(*coros)
#     pcs.clear()


# if __name__ == "__main__":

#     # app.router.add_post("/offer", offer)
