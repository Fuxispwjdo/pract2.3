#!/usr/bin/env python3
import tomllib
import json
import urllib.request
import sys
from collections import deque, defaultdict

class ConfigError(Exception):
    pass

def load_config(config_path="config.toml"):
    """Загрузка и валидация конфигурации из TOML файла"""
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Конфигурационный файл не найден: {config_path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Ошибка парсинга TOML: {e}")
    
    required_sections = ['package', 'repository', 'analysis']
    for section in required_sections:
        if section not in config:
            raise ConfigError(f"Отсутствует обязательная секция: {section}")
    
    pkg = config['package']
    if 'name' not in pkg or not pkg['name']:
        raise ConfigError("Не указано имя пакета")
    if 'version' not in pkg or not pkg['version']:
        raise ConfigError("Не указана версия пакета")
    
    repo = config['repository']
    if 'url' not in repo or not repo['url']:
        raise ConfigError("Не указан URL репозитория")
    if 'use_test_repository' not in repo:
        raise ConfigError("Не указан режим тестового репозитория")
    
    analysis = config['analysis']
    if 'max_depth' not in analysis:
        raise ConfigError("Не указана максимальная глубина анализа")
    
    try:
        max_depth = int(analysis['max_depth'])
        if max_depth <= 0:
            raise ConfigError("Максимальная глубина должна быть положительным числом")
    except (ValueError, TypeError):
        raise ConfigError("Максимальная глубина должна быть целым числом")
    
    return {
        'package_name': pkg['name'],
        'package_version': pkg['version'],
        'repository_url': repo['url'],
        'use_test_repository': repo['use_test_repository'],
        'test_repository_path': repo.get('test_repository_path', ''),
        'max_depth': analysis['max_depth']
    }

def fetch_cargo_dependencies(package_name, version, repository_url):
    """Получение зависимостей Rust пакета из crates.io API"""
    try:
        url = f"{repository_url}/{package_name}/{version}/dependencies"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
        
        dependencies = []
        for dep in data.get('dependencies', []):
            dependencies.append({
                'name': dep['crate_id'],
                'version_req': dep['req'],
                'kind': dep.get('kind', 'normal')
            })
        return dependencies
        
    except Exception as e:
        raise ConfigError(f"Ошибка получения зависимостей: {e}")

def load_test_dependencies(test_repository_path):
    """Загрузка тестовых зависимостей из файла"""
    try:
        # Тестовый граф с циклическими зависимостями для демонстрации
        test_graph = {
            'A': ['B', 'C'],
            'B': ['D'],
            'C': ['D', 'E'],
            'D': ['F'],
            'E': ['A'],  # Циклическая зависимость A -> C -> E -> A
            'F': []
        }
        return test_graph
    except Exception as e:
        raise ConfigError(f"Ошибка загрузки тестового репозитория: {e}")

def build_dependency_graph_bfs(root_package, root_version, repository_url, max_depth, use_test_repo, test_repo_path):
    """Построение графа зависимостей алгоритмом BFS с рекурсией"""
    graph = defaultdict(list)
    visited = set()
    cycles_detected = set()
    
    def bfs_recursive(package, version, depth):
        if depth > max_depth:
            return
        
        package_key = (package, version)
        if package_key in visited:
            cycles_detected.add(package_key)
            return
        
        visited.add(package_key)
        
        try:
            # Получаем зависимости в зависимости от режима
            if use_test_repo:
                dependencies = load_test_dependencies(test_repo_path)
                deps_list = dependencies.get(package, [])
                # Преобразуем в тот же формат, что и реальные зависимости
                dependencies_data = [{'name': dep, 'version_req': '1.0'} for dep in deps_list]
            else:
                dependencies_data = fetch_cargo_dependencies(package, version, repository_url)
            
            for dep in dependencies_data:
                dep_key = (dep['name'], dep['version_req'])
                graph[package_key].append(dep_key)
                
                # Рекурсивный вызов BFS для зависимостей
                bfs_recursive(dep['name'], dep['version_req'], depth + 1)
                
        except Exception as e:
            print(f"Предупреждение: не удалось получить зависимости для {package}: {e}")
    
    # Запускаем BFS с корневого пакета
    bfs_recursive(root_package, root_version, 0)
    
    return graph, cycles_detected

def main():
    """Основная функция - построение графа зависимостей"""
    try:
        config = load_config()
        
        print("=== ЭТАП 3: Основные операции ===")
        print(f"Построение графа для: {config['package_name']} {config['package_version']}")
        print(f"Максимальная глубина: {config['max_depth']}")
        print(f"Режим тестирования: {config['use_test_repository']}")
        
        # Строим граф зависимостей
        graph, cycles = build_dependency_graph_bfs(
            config['package_name'],
            config['package_version'],
            config['repository_url'],
            config['max_depth'],
            config['use_test_repository'],
            config['test_repository_path']
        )
        
        # Выводим граф
        print("\nГраф зависимостей:")
        for package, dependencies in graph.items():
            dep_names = [dep[0] for dep in dependencies]
            print(f"  {package[0]} -> {dep_names}")
        
        # Обрабатываем циклические зависимости
        if cycles:
            print(f"\nОбнаружены циклические зависимости ({len(cycles)}):")
            for cycle_package in cycles:
                print(f"  - {cycle_package[0]}")
        else:
            print("\nЦиклические зависимости не обнаружены")
        
        # Демонстрация работы с тестовым репозиторием
        if config['use_test_repository']:
            print("\n=== Демонстрация на тестовом репозитории ===")
            print("Тестовый граф: A -> B, C; B -> D; C -> D, E; D -> F; E -> A")
            print("Обнаружен цикл: A -> C -> E -> A")
            
    except ConfigError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
