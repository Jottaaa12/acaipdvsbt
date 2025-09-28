print("Iniciando teste de importação...")
try:
    print("Importando Selenium...")
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    print("Selenium importado com sucesso.")

    print("Importando whatsappy...")
    import whatsappy
    print("whatsappy importado com sucesso.")

    print("\nTeste de inicialização do WebDriver:")
    print("Chamando ChromeDriverManager().install()...")
    driver_path = ChromeDriverManager().install()
    print(f"WebDriver path: {driver_path}")

    print("Instanciando webdriver.Chrome...")
    # Não usar headless para este teste
    service = ChromeService(driver_path)
    driver = webdriver.Chrome(service=service)
    print("WebDriver instanciado com sucesso.")

    print("Navegador aberto. Fechando em 5 segundos...")
    import time
    time.sleep(5)
    driver.quit()
    print("Teste concluído com sucesso!")

except Exception as e:
    import traceback
    print("\n--- OCORREU UM ERRO ---")
    traceback.print_exc()

input("\nPressione Enter para sair.")
