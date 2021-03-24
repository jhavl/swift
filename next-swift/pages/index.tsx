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
                <Swift port={8080} />
            </main>
        </div>
    )
}

export default Home
