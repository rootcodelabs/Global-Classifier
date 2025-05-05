import Image from "next/image";
import styles from "./page.module.css";
import LoginButton from "./components/LoginButton";

export default function Home() {
  return (
    <main className={styles.main}>
      <div className={styles.center}>
        <div>
          <LoginButton />
        </div>
      </div>
    </main>
  );
}
