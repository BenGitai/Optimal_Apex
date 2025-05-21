# train_visual.py

from ai import GA, evaluate

def run_training_visual(track="test",
                        pop_size=20,
                        generations=10):
    # population of genomes
    genome_length = (7 + 1 + 2 + 1) * 3
    ga = GA(pop_size, genome_length)

    for gen in range(generations):
        print(f"\n=== Gen {gen+1}/{generations} ===")
        scored = []
        for i, genome in enumerate(ga.population, start=1):
            fit = evaluate(genome, track,
                           sim_time=20, fps=60,
                           render=False)
            print(f"  [{i}/{pop_size}] → fitness {fit:.1f}")
            scored.append((genome, fit))

        ga.evolve(scored)
        champ, best_fit = max(scored, key=lambda x:x[1])
        print(f"Best this gen: {best_fit:.1f}")

        # now *watch* the champion drive for 10s at 30FPS
        print("Visualizing champion…")
        evaluate(champ, track,
                 sim_time=10, fps=30,
                 render=True)

    return champ

if __name__ == "__main__":
    champ = run_training_visual(
        track="test",
        pop_size=20,
        generations=10
    )

    champ.save("best_genome.json")
    print("Saved best genome to best_genome.json")

    print("Done training; final champion ready.")
