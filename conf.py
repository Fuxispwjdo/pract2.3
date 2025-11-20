#!/usr/bin/env python3
import tomllib
import json
import urllib.request
import sys
import os
from collections import deque, defaultdict

class ConfigError(Exception):
    pass

def get_user_input():
    """Интерактивный ввод параметров от пользователя"""
    
    use_test_repo = input("Тестовый репозиторий? (y/n): ").lower().strip() == 'y'
    
    config = {}
    config['use_test_repository'] = use_test_repo
    
    if use_test_repo:
        test_path = input("Файл графа: ").strip()
        config['test_repository_path'] = test_path if test_path else "demo"
        config['package_name'] = "A"  # По умолчанию начинаем с A
        config['package_version'] = "1.0"
        
    else:
        config['package_name'] = input("Пакет: ").strip()
        config['package_version'] = input("Версия: ").strip()
        repo_url = input("URL репозитория: ").strip()
        config['repository_url'] = repo_url if repo_url else "https://crates.io/api/v1/crates"
    
    max_depth_input = input("Макс глубина: ").strip()
    if not max_depth_input:
        config['max_depth'] = float('inf')
    else:
        config['max_depth'] = int(max_depth_input)
    
    return config

def load_config(config_path="config.toml"):
    """Загрузка конфигурации из TOML файла"""
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Файл не найден: {config_path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Ошибка TOML: {e}")
    
    return {
        'package_name': config['package']['name'],
        'package_version': config['package']['version'],
        'repository_url': config['repository']['url'],
        'use_test_repository': config['repository']['use_test_repository'],
        'test_repository_path': config['repository'].get('test_repository_path', ''),
        'max_depth': config['analysis']['max_depth']
    }

def fetch_cargo_dependencies(package_name, version, repository_url):
    """Получение зависимостей из crates.io API"""
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

def load_test_dependencies_from_file(file_path):
    """Загрузка тестовых зависимостей из файла"""
    if not os.path.exists(file_path):
        return load_demo_dependencies()
    
    graph = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ':' in line:
                package, deps_str = line.split(':', 1)
                package = package.strip()
                dependencies = [dep.strip() for dep in deps_str.split(',') if dep.strip()]
                graph[package] = dependencies
    return graph

def load_demo_dependencies():
    """Демонстрационный граф зависимостей"""
    return {
        'A': ['B', 'C'],
        'B': ['D'],
        'C': ['A', 'E'],  # Цикл A -> C -> A
        'D': ['F'],
        'E': ['G'],
        'F': ['B'],       # Цикл B -> D -> F -> B
        'G': []
    }

def build_dependency_graph_bfs(root_package, root_version, repository_url, max_depth, use_test_repo, test_repo_path):
    """Построение графа зависимостей BFS с рекурсией"""
    graph = defaultdict(list)
    visited = {}
    cycles_detected = []
    depth_info = {}
    
    def bfs_recursive(package, version, current_depth):
        if current_depth > max_depth:
            return
        
        package_key = f"{package}@{version}"
        
        if package_key in visited:
            cycles_detected.append(f"{package_key} -> ... -> {package_key}")
            return
        
        visited[package_key] = current_depth
        depth_info[package_key] = current_depth
        
        try:
            if use_test_repo:
                if test_repo_path and test_repo_path != "demo":
                    dependencies_data = load_test_dependencies_from_file(test_repo_path)
                else:
                    dependencies_data = load_demo_dependencies()
                
                deps_list = dependencies_data.get(package, [])
                dependencies = [{'name': dep, 'version_req': '1.0'} for dep in deps_list]
            else:
                dependencies = fetch_cargo_dependencies(package, version, repository_url)
            
            for dep in dependencies:
                dep_key = f"{dep['name']}@{dep['version_req']}"
                graph[package_key].append(dep_key)
                bfs_recursive(dep['name'], dep['version_req'], current_depth + 1)
                
        except Exception as e:
            print(f"Ошибка для {package}: {e}")
        
        visited.pop(package_key)
    
    bfs_recursive(root_package, root_version, 0)
    return graph, cycles_detected, depth_info

def print_dependency_tree(graph, cycles, depth_info, root_package, max_depth):
    """Вывод дерева зависимостей"""
    print(f"\nГраф для {root_package}")
    print(f"Глубина: {max_depth if max_depth != float('inf') else 'не ограничена'}")
    print(f"Пакетов: {len(graph)}")
    
    packages_by_depth = defaultdict(list)
    for package, depth in depth_info.items():
        packages_by_depth[depth].append(package)
    
    for depth in sorted(packages_by_depth.keys()):
        print(f"\nУровень {depth}:")
        for package in sorted(packages_by_depth[depth]):
            deps = graph.get(package, [])
            indent = "  " * depth
            if deps:
                print(f"{indent}{package} -> {', '.join(deps)}")
            else:
                print(f"{indent}{package}")
    
    if cycles:
        print(f"\nЦиклы: {len(cycles)}")
        for cycle in cycles:
            print(f"  {cycle}")

def save_graph_to_file(graph, cycles, depth_info, root_package, max_depth, filename):
    """Сохранение графа в файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Граф для {root_package}\n")
            f.write(f"# Глубина: {max_depth if max_depth != float('inf') else 'не ограничена'}\n")
            f.write(f"# Пакетов: {len(graph)}\n")
            
            for package, dependencies in graph.items():
                if dependencies:
                    f.write(f"{package}: {', '.join(dependencies)}\n")
            
            if cycles:
                f.write("\n# Циклы:\n")
                for cycle in cycles:
                    f.write(f"# {cycle}\n")
        
        print(f"Сохранено: {filename}")
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

def main():
    """Основная функция"""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--config":
            config_path = sys.argv[2] if len(sys.argv) > 2 else "config.toml"
            config = load_config(config_path)
        else:
            config = get_user_input()
        
        graph, cycles, depth_info = build_dependency_graph_bfs(
            config['package_name'],
            config.get('package_version', '1.0'),
            config.get('repository_url', 'https://crates.io/api/v1/crates'),
            config['max_depth'],
            config['use_test_repository'],
            config.get('test_repository_path', '')
        )
        
        root_package_key = f"{config['package_name']}@{config.get('package_version', '1.0')}"
        print_dependency_tree(graph, cycles, depth_info, root_package_key, config['max_depth'])
        
        output_file = f"dep_{config['package_name']}.txt"
        save_graph_to_file(graph, cycles, depth_info, root_package_key, config['max_depth'], output_file)
        
    except ConfigError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
