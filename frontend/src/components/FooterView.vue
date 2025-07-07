<template>
  <footer>
    <div class="logo__container">
      <img class="logo" src="../assets/logos/uzh.svg" alt="UZH">
    </div>
    <hr>
    Copyright &copy; 2024 LiRI 
    | 
    <a style="color: white;" href="mailto:lcp@linguistik.uzh.ch?subject=Bug%20report">{{ $t('footer-report') }}</a>
  </footer>
</template>

<style scoped>
.logo {
  height: 60px;
}

.logo__container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.logo__divider {
  height: 60px;
  border-right: 1px solid white;
}

footer {
  text-align: center;
  width: 100%;
  font-size: 12px;
  margin-top: 50px;
  padding: 30px 0 15px;
  color: #fff;
  background-color: #2a7f62;
}

hr {
  margin-top: 30px;
}

@media (max-width: 500px) {
  .logo__container {
    flex-direction: column;
  }

  .logo__divider {
    display: none;
  }
}
</style>

<script>
export default {
  name: "FooterView",
};
</script>
