import os

from sandbox.gkahn.rnn_critic.examples.run_rnn_critic import main as run_main
from sandbox.gkahn.rnn_critic.scripts.analyze_experiment import main as analyze_main

if __name__ == '__main__':
    # parser = argparse.ArgumentParser()
    # parser.add_argument('exps', type=str)
    # args = parser.parse_args()
    # exps = args.exps.split()

    gpu_device = 1
    # exps = ['exp{0}'.format(i) for i in range(291, 315)]
    exps = ['test']

    for exp in exps:
        # try:
        # print('Running {0}'.format(exp))
        # run_main(os.path.abspath('examples/yamls/{0}.yaml'.format(exp)))
        print('Analyzing {0}'.format(exp))
        analyze_main(exp, skip_itr=1, max_itr=int(1e4), gpu_device=gpu_device)
        # except:
        #     print('Error analyzing {0}'.format(exp))