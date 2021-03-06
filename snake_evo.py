import numpy as np

from copy import deepcopy

from snake_game import SnakeGame, GraphicalSnakeGame

from time import sleep

from random import choices

from tqdm import tqdm


INPUT_SIZE = 5 #change if the number of sensors changes
OUTPUT_SIZE = 3 #probably won't change but just in case

BEHAVIORS = ["forward", "left", "right"]

def mutate_array(array, prob, strength):
    """Every 1/prob element in the array is mutated with a standard deviation of strength."""
    m = np.random.normal(0, strength, array.shape)
    p = (np.random.random(array.shape) < prob)
    return array+(m*p)

def sigmoid(x):
    """calculate the sigmoid function of x"""
    return 1/(np.exp(-x) + 1)

def relu(x):
    return np.maximum(0,x)


class Agent:
    def __init__(
        self,
        blocks_width,
        blocks_height,
        hidden_sizes
    ):
        self.blocks_width = blocks_width
        self.blocks_height = blocks_height
        self.scale_factor = (blocks_width+blocks_height)//2
        self.hidden_sizes = hidden_sizes
        self.hidden_layers = []
        self.biases = []
        self.recursive = np.zeros([self.hidden_sizes[-1]])

        for i,j in zip([INPUT_SIZE+self.hidden_sizes[-1]]+self.hidden_sizes, self.hidden_sizes + [OUTPUT_SIZE]):
            self.hidden_layers.append(np.random.normal(0,1,[i,j]))
            self.biases.append(np.random.normal(0,1,[j]))

    def reset_recursive(self):
        self.recursive *= 0

    def predict(self, in_coords, activation=np.arctan):
        in_coords = np.array(in_coords)/self.scale_factor
        work = np.concatenate([in_coords, self.recursive])
        for h,b in zip(self.hidden_layers[:-1], self.biases[:-1]):
            work = activation(work @ h + b)
        self.recursive = work
        return activation(work @ self.hidden_layers[-1] + self.biases[-1])

    def play(
        self,
        blocks_height,
        blocks_width,
        threshold = 100,
        activation = np.arctan,
        graphical = False,
        diag = False,
        block_size = 30,
        tick = 0
    ):
        """
        Run the agent through a game of snake.
        blocks_height, blocks_width are size of grid
        threshold is how many turns are allowed without scoring
        graphical = True to play game on screen
        diag = True to show diagnostic lines on screen
        block_size is pixel size of blocks
        tick is how many seconds to wait between frames
        """
        self.reset_recursive()

        if graphical:
            game = GraphicalSnakeGame(
                blocks_width=blocks_width,
                blocks_height = blocks_height,
                block_size=block_size
            )
        else:
            game = SnakeGame(
                blocks_width=blocks_width,
                blocks_height = blocks_height
            )
        alive = game.step()
        score = game.score()
        counter = 0
        total_steps = 0
        while counter < threshold and alive:
            counter += 1
            total_steps += 1

            #get the agent's action for this turn
            guess = self.predict(game.get_values(), activation=activation)

            #input the agent's action to the game object and move
            game.turn(BEHAVIORS[np.argmax(guess)])
            alive = game.step()

            #Check for score increase
            new_score = game.score()
            if new_score > score:
                score = new_score
                counter = 0

            #Draw to screen if desired
            if graphical:
                game.draw(diag)
                sleep(tick)
        return score, total_steps, alive
            


    def mutate(self, prob = 0.05, strength = 1):
        """Returns a mutated copy of self."""
        out = deepcopy(self)
        out.reset_recursive()
        out.hidden_layers = [mutate_array(a, prob, strength) for a in out.hidden_layers]
        out.biases = [mutate_array(a, prob, strength) for a in out.biases]
        return out
            

class Population:
    """a population of snake playing neural agents"""
    def __init__(
        self,
        n_pop,
        blocks_width,
        blocks_height,
        hidden_sizes
    ):
        self.n_pop = n_pop
        self.blocks_width = blocks_width
        self.blocks_height = blocks_height
        self.hidden_sizes = hidden_sizes
        self.pop = \
            [Agent(blocks_width, blocks_height, hidden_sizes) for i in range(self.n_pop)]
        self.scores = np.zeros([n_pop])
    
    def play(self, n_trials, threshold = 100, walk_penalty = 0.01, activation = np.arctan):
        for i, ag in enumerate(self.pop):
            for _ in range(n_trials):
                sc, tot, _alive = ag.play(
                    self.blocks_height,
                    self.blocks_width,
                    threshold = threshold,
                    activation = activation
                )
                self.scores[i]+=sc - 2 - (tot * walk_penalty)
        self.scores = np.maximum(self.scores, 0)

    def generation(self, num_elites = 2, prob= 0.05, strength=1):
        old_pop = deepcopy(self.pop)
        elite_index = np.argsort(self.scores)[-num_elites:]
        elites = [old_pop[i] for i in elite_index]
        for i in elites:
            i.reset_recursive()
        new_gen = choices(old_pop,k=self.n_pop-num_elites, weights=self.scores)
        self.pop = [i.mutate(prob, strength) for i in new_gen] + elites
        best = deepcopy(old_pop[np.argmax(self.scores)])
        self.scores *= 0
        return best

    def ensemble(
        self,
        blocks_height,
        blocks_width,
        threshold = 100,
        activation = np.arctan,
        graphical = True,
        diag = True,
        block_size = 30,
        tick = 0.1
    ):
        """Weight the population by their scores and use that as an ensemble learner to play Snake."""
        if self.scores.sum() == 0:
            raise ValueError("Need nonzero scores to ensemble. Try running play().")
        for ag in self.pop:
            ag.reset_recursive()
        
        if graphical:
            game = GraphicalSnakeGame(
                blocks_width=blocks_width,
                blocks_height = blocks_height,
                block_size=block_size
            )
        else:
            game = SnakeGame(
                blocks_width=blocks_width,
                blocks_height = blocks_height
            )

        alive = game.step()
        score = game.score()
        counter = 0
        while counter < threshold and alive:
            counter += 1

            #get the ensemble agent's action for this turn
            val = game.get_values()
            guess = sum([ag.predict(val, activation= activation)*sc for ag, sc in zip(self.pop, self.scores)])


            #input the agent's action to the game object and move
            game.turn(BEHAVIORS[np.argmax(guess)])
            alive = game.step()

            #Check for score increase
            new_score = game.score()
            if new_score > score:
                score = new_score
                counter = 0

            #Draw to screen if desired
            if graphical:
                game.draw(diag)
                sleep(tick)
        return score, alive

if __name__ == "__main__":
    P = Population(
        n_pop = 100,
        blocks_width=15,
        blocks_height = 10,
        hidden_sizes = [10,10]
    )

    best = P.pop[0]

    tq=tqdm(range(1000))

    for i in tq:
        P.play(n_trials = 5, threshold = 50, activation=relu, walk_penalty=0)
        # if i%10 == 0:
        #     score, _ = P.ensemble(
        #         blocks_height = P.blocks_height,
        #         blocks_width = P.blocks_width,
        #         threshold = 100,
        #         activation=relu,
        #         graphical=True,
        #         diag=True,
        #         block_size=30,
        #         tick=0.1
        #     )
        tq.set_postfix({"max_score":max(P.scores), "avg_score":np.mean(P.scores)})
        best = P.generation(prob = 0.025, strength = 2)
        if i % 10 == 0:
            best.play(
                blocks_height = P.blocks_height,
                blocks_width = P.blocks_width,
                threshold = 100,
                activation=relu,
                graphical=True,
                diag=True,
                block_size=30,
                tick=0.1
            )

        
