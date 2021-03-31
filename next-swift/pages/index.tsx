import Head from 'next/head'
import styles from '../styles/Home.module.css'
import Swift from '../components/Swift'

const Home = () => {
    return (
        <div className={styles.container}>
            <Head>
                <title>Create Next App</title>
                <link rel="icon" href="/favicon.ico" />
            </Head>

            <main className={styles.main}>
                <div className={styles.container}>
                    {/* <div class="info">
                    <div id="fps">60 fps</div>
                    <div id="sim-time">00:00.000</div>
                    </div> */}

                    <Swift port={0} />
                </div>
            </main>
        </div>
    )
}

export default Home
