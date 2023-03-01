import { useEffect, useRef, lazy } from 'react'
import Head from 'next/head'
import styles from '../styles/Home.module.css'
// import Swift from '../components/Swift'
import Swift from 'react-swift'

const Home = () => {
    // const pc = useRef<RTCPeerConnection>(null)

    // const negotiate = () => {
    //     return pc.current.createOffer().then(function(offer) {
    //         return pc.current.setLocalDescription(offer);
    //     }).then(function() {
    //         // wait for ICE gathering to complete
    //         return new Promise<void>((resolve) => {
    //             if (pc.current.iceGatheringState === 'complete') {
    //                 resolve();
    //             } else {
    //                 const checkState = () => {
    //                     if (pc.current.iceGatheringState === 'complete') {
    //                         pc.current.removeEventListener('icegatheringstatechange', checkState);
    //                         resolve();
    //                     }
    //                 }
    //                 pc.current.addEventListener('icegatheringstatechange', checkState);
    //             }
    //         });
    //     }).then(function() {
    //         var offer = pc.current.localDescription;

    //         return fetch('/offer', {
    //             body: JSON.stringify({
    //                 sdp: offer.sdp,
    //                 type: offer.type,
    //             }),
    //             headers: {
    //                 'Content-Type': 'application/json'
    //             },
    //             method: 'POST'
    //         });
    //     }).then(function(response) {
    //         return response.json();
    //     }).then(function(answer) {
    //         return pc.current.setRemoteDescription(answer);
    //     }).catch(function(e) {
    //         alert(e);
    //     });
    // }

    // useEffect(() => {
    //     // const config = {
    //     //     sdpSemantics: 'unified-plan'
    //     // };

    //     pc.current = new RTCPeerConnection();

    //     // Connect video
    //     pc.current.addEventListener('track', (evt) => {
    //         if (evt.track.kind == 'video') {
    //             const video = document.getElementById('video')
    //             // video.src = evt.streams[0];
    //         }
    //     });

    //     const constraints = {
    //         video: {
    //             width: 640,
    //             height: 480
    //         }
    //     };

    //     navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
    //         stream.getTracks().forEach(function(track) {
    //             pc.current.addTrack(track, stream);
    //         });
    //         return negotiate();
    //     }, function(err) {
    //         alert('Could not acquire media: ' + err);
    //     });

    // }, [])

    return (
        <div className={styles.container}>
            <Head>
                <title>Swift</title>
                <link rel="icon" href="/favicon.ico" />
                <meta http-equiv='cache-control' content='no-cache' />
                <meta http-equiv='expires' content='0' />
                <meta http-equiv='pragma' content='no-cache' />
            </Head>

            <main className={styles.main}>
                <div className={styles.container}>
                    {/* <div class="info">
                    <div id="fps">60 fps</div>
                    <div id="sim-time">00:00.000</div>
                    </div> */}

                    <Swift port={0} />
                </div>
                {/* <video id="video" autoPlay={true} playsInline={true}></video> */}
            </main>
        </div>
    )
}

export default Home
